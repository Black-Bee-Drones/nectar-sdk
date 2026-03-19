/**
 * depth_cluster_node.cpp
 *
 * ROS2 node for BFS-based depth clustering obstacle detection.
 *
 * This version subscribes to a depth image topic (sensor_msgs/Image) instead
 * of opening a RealSense pipeline directly, making it compatible with
 * realsense-ros / Isaac ROS or any other depth source.
 *
 * Post-processing is done with the OpenCV-based filters from depth_filters.hpp
 * (which re-implement the Intel RS2 algorithms for cv::Mat data).
 *
 * Publishes obstacle information on:
 *   /<namespace>/obstacle_detected  (std_msgs/Bool)
 *   /<namespace>/obstacle_distance  (std_msgs/Float32)   — meters
 *   /<namespace>/obstacle_direction (std_msgs/String)    — FRONT | LEFT | RIGHT
 *
 * Parameters (ROS2):
 *   namespace            (string,  default "obstacle_detection")
 *   depth_topic          (string,  default "/camera/depth/image_rect_raw")
 *   depth_scale          (double,  default 0.001)  — multiplier to convert raw depth to metres
 *   fov_h                (double,  default 87.0)   — horizontal field of view in degrees
 *   fov_v                (double,  default 58.0)   — vertical field of view in degrees
 *   decimation_scale     (int,     default 2)      — decimation factor (1 = disable)
 *   depth_threshold      (double,  default 0.06)   — max depth delta (m) to merge pixels
 *   min_group_size       (int,     default 300)     — minimum cluster pixel count
 *   max_obstacle_distance(double,  default 1.0)    — clusters beyond this (m) are ignored
 *   drone_radius         (double,  default 0.25)   — used for FOV-based threshold matrix
 */

#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/bool.hpp>
#include <std_msgs/msg/float32.hpp>
#include <std_msgs/msg/string.hpp>
#include <sensor_msgs/msg/image.hpp>

#include <cv_bridge/cv_bridge.h>
#include <opencv2/opencv.hpp>

#include "depth_filters.hpp"

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
        this->declare_parameter<std::string>("depth_topic", "/camera/depth/image_rect_raw");
        this->declare_parameter<double>("depth_scale", 0.001);
        this->declare_parameter<double>("fov_h", 87.0);
        this->declare_parameter<double>("fov_v", 58.0);
        this->declare_parameter<int>("decimation_scale", 2);
        this->declare_parameter<double>("depth_threshold", 0.06);
        this->declare_parameter<int>("min_group_size", 300);
        this->declare_parameter<double>("max_obstacle_distance", 1.0);
        this->declare_parameter<double>("drone_radius", 0.25);

        ns_                    = this->get_parameter("namespace").as_string();
        depth_topic_           = this->get_parameter("depth_topic").as_string();
        depth_scale_           = static_cast<float>(this->get_parameter("depth_scale").as_double());
        fov_h_                 = static_cast<float>(this->get_parameter("fov_h").as_double());
        fov_v_                 = static_cast<float>(this->get_parameter("fov_v").as_double());
        depth_threshold_       = static_cast<float>(this->get_parameter("depth_threshold").as_double());
        min_group_size_        = this->get_parameter("min_group_size").as_int();
        max_obstacle_distance_ = static_cast<float>(this->get_parameter("max_obstacle_distance").as_double());
        drone_radius_          = static_cast<float>(this->get_parameter("drone_radius").as_double());

        int dec_scale = this->get_parameter("decimation_scale").as_int();
        decimate_ = nectar::DepthDecimationFilter(dec_scale);

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
        // Depth image subscriber
        // ----------------------------------------------------------------
        depth_sub_ = this->create_subscription<sensor_msgs::msg::Image>(
            depth_topic_, 10,
            std::bind(&DepthClusterNode::depth_callback, this, std::placeholders::_1));

        RCLCPP_INFO(this->get_logger(),
            "DepthClusterNode started — subscribing to %s, publishing on /%s/*",
            depth_topic_.c_str(), ns_.c_str());
    }

private:
    // ----------------------------------------------------------------
    // Depth callback — replaces the timer + rs2::pipeline polling
    // ----------------------------------------------------------------
    void depth_callback(const sensor_msgs::msg::Image::ConstSharedPtr& msg)
    {
        // Convert ROS Image to cv::Mat
        cv_bridge::CvImageConstPtr cv_ptr;
        try
        {
            cv_ptr = cv_bridge::toCvShare(msg);
        }
        catch (const cv_bridge::Exception& e)
        {
            RCLCPP_ERROR_THROTTLE(this->get_logger(), *this->get_clock(), 2000,
                "cv_bridge error: %s", e.what());
            return;
        }

        cv::Mat depth_raw = cv_ptr->image;

        // Apply decimation filter on raw data
        cv::Mat decimated = decimate_.apply(depth_raw);

        const int width  = decimated.cols;
        const int height = decimated.rows;

        // Convert to float metres
        cv::Mat depth_float;
        if (decimated.type() == CV_16U)
            decimated.convertTo(depth_float, CV_32F, depth_scale_);
        else if (decimated.type() == CV_32F)
            depth_float = decimated.clone();
        else
        {
            RCLCPP_ERROR_THROTTLE(this->get_logger(), *this->get_clock(), 5000,
                "Unsupported depth encoding: %s", msg->encoding.c_str());
            return;
        }

        // Rebuild threshold matrix if image dimensions changed
        if (thresh_mat_.empty() || thresh_mat_.cols != width || thresh_mat_.rows != height)
        {
            float fov[2] = {fov_h_, fov_v_};
            thresh_mat_ = threshold_matrix(max_obstacle_distance_, drone_radius_, fov, width, height);
            RCLCPP_INFO(this->get_logger(),
                "Threshold matrix built for %dx%d (FOV %.1f x %.1f deg)",
                width, height, fov_h_, fov_v_);
        }

        // Apply threshold matrix — zero out pixels beyond adaptive distance
        depth_float.setTo(0, depth_float >= thresh_mat_);

        // ----------------------------------------------------------------
        // BFS clustering (identical algorithm to original)
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
    // Depth filter
    // ----------------------------------------------------------------
    nectar::DepthDecimationFilter decimate_;

    // ----------------------------------------------------------------
    // Parameters
    // ----------------------------------------------------------------
    std::string ns_;
    std::string depth_topic_;
    float       depth_scale_{0.001f};
    float       fov_h_{87.0f};
    float       fov_v_{58.0f};
    float       depth_threshold_;
    int         min_group_size_;
    float       max_obstacle_distance_;
    float       drone_radius_;
    cv::Mat     thresh_mat_;

    // ----------------------------------------------------------------
    // ROS subscriber
    // ----------------------------------------------------------------
    rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr depth_sub_;

    // ----------------------------------------------------------------
    // Publishers
    // ----------------------------------------------------------------
    rclcpp::Publisher<std_msgs::msg::Bool>::SharedPtr    pub_detected_;
    rclcpp::Publisher<std_msgs::msg::Float32>::SharedPtr pub_distance_;
    rclcpp::Publisher<std_msgs::msg::String>::SharedPtr  pub_direction_;
};

int main(int argc, char ** argv)
{
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<DepthClusterNode>());
    rclcpp::shutdown();
    return 0;
}
