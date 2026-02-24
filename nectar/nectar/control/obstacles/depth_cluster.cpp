/**
 * depth_cluster_node.cpp
 *
 * ROS2 node that captures depth frames from a RealSense camera via librealsense2,
 * runs a BFS-based depth clustering algorithm, and publishes obstacle information
 * on the three topics consumed by ROSObstacleDetector:
 *
 *   /<namespace>/obstacle_detected  (std_msgs/Bool)
 *   /<namespace>/obstacle_distance  (std_msgs/Float32)   — meters
 *   /<namespace>/obstacle_direction (std_msgs/String)    — FRONT | LEFT | RIGHT
 *
 * Parameters (ROS2):
 *   namespace            (string,  default "obstacle_detection")
 *   depth_threshold      (double,  default 0.06)   — max depth delta (m) to merge pixels
 *   min_group_size       (int,     default 300)     — minimum cluster pixel count
 *   max_obstacle_distance (double, default 1.0)    — clusters beyond this (m) are ignored
 */

#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/bool.hpp>
#include <std_msgs/msg/float32.hpp>
#include <std_msgs/msg/string.hpp>

#include <librealsense2/rs.hpp>
#include <opencv2/opencv.hpp>

#include <chrono>
#include <cmath>
#include <limits>
#include <queue>
#include <string>
#include <vector>

class DepthClusterNode : public rclcpp::Node
{
public:
    DepthClusterNode()
    : Node("depth_cluster_node")
    {
        // ----------------------------------------------------------------
        // Parameters
        // ----------------------------------------------------------------
        this->declare_parameter<std::string>("namespace", "obstacle_detection");
        this->declare_parameter<double>("depth_threshold", 0.06);
        this->declare_parameter<int>("min_group_size", 300);
        this->declare_parameter<double>("max_obstacle_distance", 1.0);
        this->declare_parameter<double>("drone_radius", 0.25);

        ns_                   = this->get_parameter("namespace").as_string();
        depth_threshold_      = static_cast<float>(this->get_parameter("depth_threshold").as_double());
        min_group_size_       = this->get_parameter("min_group_size").as_int();
        max_obstacle_distance_= static_cast<float>(this->get_parameter("max_obstacle_distance").as_double());
        drone_radius_         = static_cast<float>(this->get_parameter("drone_radius").as_double());

        // ----------------------------------------------------------------
        // Publishers
        // ----------------------------------------------------------------
        pub_detected_  = this->create_publisher<std_msgs::msg::Bool>(
            "/" + ns_ + "/obstacle_detected", 10);
        pub_distance_  = this->create_publisher<std_msgs::msg::Float32>(
            "/" + ns_ + "/obstacle_distance", 10);
        pub_direction_ = this->create_publisher<std_msgs::msg::String>(
            "/" + ns_ + "/obstacle_direction", 10);

        // ----------------------------------------------------------------
        // RealSense pipeline — same stream config as the original standalone app
        // ----------------------------------------------------------------
        rs2::config cfg;
        cfg.enable_stream(RS2_STREAM_DEPTH, 640, 480, RS2_FORMAT_Z16, 90);
        rs2::pipeline_profile profile = pipe_.start(cfg);
        auto depth_stream = profile.get_stream(RS2_STREAM_DEPTH)
                             .as<rs2::video_stream_profile>();
        auto i = depth_stream.get_intrinsics();
        float fov[2]; // X, Y fov
        rs2_fov(&i, fov);

        std::cout << "Camera FOV: " << fov[0] << " x " << fov[1] << " degrees" << std::endl;

        rs2::device dev = pipe_.get_active_profile().get_device();
        rs2::depth_sensor depth_sensor = dev.first<rs2::depth_sensor>();
        depth_scale_ = depth_sensor.get_depth_scale();

        // Disable the IR projector (same as original)
        if (depth_sensor.supports(RS2_OPTION_EMITTER_ENABLED))
            depth_sensor.set_option(RS2_OPTION_EMITTER_ENABLED, 0.f);

        // Post-processing filters (same as original; spatial / hole-filling kept commented)
        decimate_  = rs2::decimation_filter();
        // rs2::spatial_filter spatial;
        // rs2::hole_filling_filter hole_filling(1);
        //threshold_ = rs2::threshold_filter(0.15f, 1.f);

        thresh_mat_ = threshold_matrix(max_obstacle_distance_, drone_radius_, fov, i.width / 2, i.height / 2);

        // ----------------------------------------------------------------
        // Timer — poll at ~90 Hz to match the camera framerate
        // ----------------------------------------------------------------
        timer_ = this->create_wall_timer(
            std::chrono::milliseconds(11),
            std::bind(&DepthClusterNode::process_frame, this));

        RCLCPP_INFO(this->get_logger(),
            "DepthClusterNode started — publishing on /%s/*", ns_.c_str());
    }

    ~DepthClusterNode()
    {
        pipe_.stop();
    }

private:
    // ----------------------------------------------------------------
    // Main processing callback
    // ----------------------------------------------------------------
    void process_frame()
    {
        rs2::frameset frames;
        if (!pipe_.poll_for_frames(&frames))
            return;

        rs2::depth_frame depth = frames.get_depth_frame();

        // Apply post-processing filters (same order as original)
        depth = decimate_.process(depth);

        const int width  = depth.get_width();
        const int height = depth.get_height();

        // Convert raw 16-bit depth to float metres (same conversion as original)
        cv::Mat depth_mat(height, width, CV_16U, (void*)depth.get_data());
        cv::Mat depth_float;
        depth_mat.convertTo(depth_float, CV_32F, depth_scale_);
        depth_float.setTo(0, depth_float >= thresh_mat_); // Apply threshold matrix

        // ----------------------------------------------------------------
        // BFS clustering (identical algorithm to original standalone app)
        // ----------------------------------------------------------------
        cv::Mat visited = cv::Mat::zeros(height, width, CV_8U);
        cv::Mat labels  = cv::Mat::zeros(height, width, CV_32S);
        int group_id = 1;

        for (int y = 0; y < height; y++)
        {
            for (int x = 0; x < width; x++)
            {
                if (visited.at<uchar>(y, x))
                    continue;

                float d = depth_float.at<float>(y, x);
                if (d == 0.f)
                    continue;

                std::queue<cv::Point> q;
                q.push({x, y});
                visited.at<uchar>(y, x) = 1;
                labels.at<int>(y, x)    = group_id;

                while (!q.empty())
                {
                    cv::Point p = q.front();
                    q.pop();

                    float base_depth = depth_float.at<float>(p.y, p.x);

                    static constexpr int dx[4] = {-1, 1,  0, 0};
                    static constexpr int dy[4] = { 0, 0, -1, 1};

                    for (int i = 0; i < 4; i++)
                    {
                        int nx = p.x + dx[i];
                        int ny = p.y + dy[i];

                        if (nx >= 0 && nx < width && ny >= 0 && ny < height)
                        {
                            if (!visited.at<uchar>(ny, nx))
                            {
                                float nd = depth_float.at<float>(ny, nx);
                                if (nd == 0.f)
                                    continue;

                                if (std::abs(nd - base_depth) < depth_threshold_)
                                {
                                    visited.at<uchar>(ny, nx) = 1;
                                    labels.at<int>(ny, nx)    = group_id;
                                    q.push({nx, ny});
                                }
                            }
                        }
                    }
                }

                group_id++;
            }
        }

        // ----------------------------------------------------------------
        // Analyse clusters — compute bounding X range and mean depth.
        // Direction logic mirrors DepthObstacleDetector in depth_camera.py.
        // ----------------------------------------------------------------
        const float img_cx = width / 2.0f;
        std::vector<float> cluster_min_x;
        std::vector<float> cluster_max_x;
        std::vector<float> cluster_depths;

        for (int id = 1; id < group_id; id++)
        {
            cv::Mat mask = (labels == id);
            int cnt = cv::countNonZero(mask);
            if (cnt < min_group_size_)
                continue;

            cv::Mat locs;
            cv::findNonZero(mask, locs);

            float mn_x = std::numeric_limits<float>::max();
            float mx_x = std::numeric_limits<float>::lowest();
            double depth_sum = 0.0;

            for (int k = 0; k < locs.rows; k++)
            {
                cv::Point pt = locs.at<cv::Point>(k);
                mn_x      = std::min(mn_x, static_cast<float>(pt.x));
                mx_x      = std::max(mx_x, static_cast<float>(pt.x));
                depth_sum += depth_float.at<float>(pt.y, pt.x);
            }

            float mean_depth = static_cast<float>(depth_sum / cnt);

            // Discard clusters beyond the configured detection range
            if (mean_depth > max_obstacle_distance_)
                continue;

            cluster_min_x.push_back(mn_x);
            cluster_max_x.push_back(mx_x);
            cluster_depths.push_back(mean_depth);

            RCLCPP_INFO_THROTTLE(this->get_logger(), *this->get_clock(), 1000,
                "Cluster %d: depth=%.2fm, x=[%.1f, %.1f], pixels=%d",
                id, mean_depth, mn_x, mx_x, cnt);
        }

        // ----------------------------------------------------------------
        // Publish obstacle_detected
        // ----------------------------------------------------------------
        const bool any_detected = !cluster_depths.empty();

        std_msgs::msg::Bool det_msg;
        det_msg.data = any_detected;
        pub_detected_->publish(det_msg);

        if (!any_detected)
            return;

        // ----------------------------------------------------------------
        // Determine direction (same logic as depth_camera.py)
        //   all clusters left  of centre → obstacle is to the RIGHT
        //   all clusters right of centre → obstacle is to the LEFT
        //   otherwise                   → FRONT
        // ----------------------------------------------------------------
        bool all_left  = true;
        bool all_right = true;

        for (size_t i = 0; i < cluster_min_x.size(); i++)
        {
            if (cluster_max_x[i] >= img_cx) all_left  = false;
            if (cluster_min_x[i] <= img_cx) all_right = false;
        }

        std::string direction;
        if (all_left)
            direction = "RIGHT";
        else if (all_right)
            direction = "LEFT";
        else
            direction = "FRONT";

        std_msgs::msg::String dir_msg;
        dir_msg.data = direction;
        pub_direction_->publish(dir_msg);

        // ----------------------------------------------------------------
        // Compute and publish average distance across all valid clusters
        // ----------------------------------------------------------------
        float total_depth = 0.f;
        for (float d : cluster_depths)
            total_depth += d;
        float avg_depth = total_depth / static_cast<float>(cluster_depths.size());

        std_msgs::msg::Float32 dist_msg;
        dist_msg.data = avg_depth;
        pub_distance_->publish(dist_msg);

        RCLCPP_INFO_THROTTLE(this->get_logger(), *this->get_clock(), 1000,
            "Obstacle detected | direction: %s | distance: %.2fm",
            direction.c_str(), avg_depth);
    }

    cv::Mat threshold_matrix(float max_depth, float radius, float fov[2], int width, int height)
    {
        cv::Mat thresh_mat(height, width, CV_32F);
        const float cx = width  / 2.0f;
        const float cy = height / 2.0f;
        const float hf_ppx = fov[0] * static_cast<float>(CV_PI) / 180.0f / width;  // radians per pixel horizontal
        const float vf_ppx = fov[1] * static_cast<float>(CV_PI) / 180.0f / height; // radians per pixel vertical

        for (int y = 0; y < height; y++)
        {
            for (int x = 0; x < width; x++)
            {
                const float sh = std::sin(hf_ppx * (x - cx));
                const float sv = std::sin(vf_ppx * (y - cy));
                const float denom = sh * sh + sv * sv;

                // At the optical centre both sin terms are ~0; cap to max_depth
                float depth = (denom > 1e-12f)
                    ? radius / std::sqrt(denom)
                    : max_depth;

                thresh_mat.at<float>(y, x) = std::min(depth, max_depth);
            }
        }

        return thresh_mat;
    }

    // ----------------------------------------------------------------
    // RealSense
    // ----------------------------------------------------------------
    rs2::pipeline           pipe_;
    rs2::decimation_filter  decimate_;
    rs2::threshold_filter   threshold_;
    float                   depth_scale_{1.0f};

    // ----------------------------------------------------------------
    // Parameters
    // ----------------------------------------------------------------
    std::string ns_;
    float       depth_threshold_;
    int         min_group_size_;
    float       max_obstacle_distance_;
    float       drone_radius_;
    cv::Mat     thresh_mat_;

    // ----------------------------------------------------------------
    // Publishers
    // ----------------------------------------------------------------
    rclcpp::Publisher<std_msgs::msg::Bool>::SharedPtr    pub_detected_;
    rclcpp::Publisher<std_msgs::msg::Float32>::SharedPtr pub_distance_;
    rclcpp::Publisher<std_msgs::msg::String>::SharedPtr  pub_direction_;

    rclcpp::TimerBase::SharedPtr timer_;
};

int main(int argc, char ** argv)
{
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<DepthClusterNode>());
    rclcpp::shutdown();
    return 0;
}

