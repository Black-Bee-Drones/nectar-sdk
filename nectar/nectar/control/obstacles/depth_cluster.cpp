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
 *
 * The pipeline operates entirely in uint16_t raw sensor units (typically mm)
 * to maximise throughput on constrained platforms (RPi4).  Parameters are
 * specified in metres for readability and converted to raw units at init.
 * Float conversion only happens when publishing scalar results.
 */

#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/bool.hpp>
#include <std_msgs/msg/float32.hpp>
#include <std_msgs/msg/float32_multi_array.hpp>
#include <sensor_msgs/msg/image.hpp>

#include <cv_bridge/cv_bridge.hpp>
#include <opencv2/opencv.hpp>

#include "depth_filters.hpp"

#include <cmath>
#include <string>
#include <vector>
#include <chrono>

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
        this->declare_parameter<std::string>("depth_topic", "/camera/camera/depth/image_rect_raw");
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
        min_group_size_        = this->get_parameter("min_group_size").as_int();
        drone_radius_          = static_cast<float>(this->get_parameter("drone_radius").as_double());

        // Convert user-facing metre parameters to raw sensor units (uint16)
        const float inv_scale = 1.0f / depth_scale_;
        depth_threshold_raw_   = static_cast<uint16_t>(
            this->get_parameter("depth_threshold").as_double() * inv_scale);
        max_obstacle_dist_raw_ = static_cast<uint16_t>(
            this->get_parameter("max_obstacle_distance").as_double() * inv_scale);

        int dec_scale = this->get_parameter("decimation_scale").as_int();
        decimate_ = nectar::DepthDecimationFilter(dec_scale);

        // ----------------------------------------------------------------
        // Publishers
        // ----------------------------------------------------------------
        pub_detected_  = this->create_publisher<std_msgs::msg::Bool>(
            "/" + ns_ + "/obstacle_detected", 10);
        pub_distance_  = this->create_publisher<std_msgs::msg::Float32>(
            "/" + ns_ + "/obstacle_distance", 10);
        pub_bboxes_ = this->create_publisher<std_msgs::msg::Float32MultiArray>(
            "/" + ns_ + "/obstacle_bboxes", 10);

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
    std::vector<double> decimation_cost;
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

        // Ensure we have a CV_16U image — the native format from RealSense
        cv::Mat depth_u16;
        if (depth_raw.type() == CV_16U) {
            depth_u16 = depth_raw;
        }
        else if (depth_raw.type() == CV_32F) {
            // Rare path: convert float metres back to raw uint16
            depth_raw.convertTo(depth_u16, CV_16U, 1.0 / depth_scale_);
        }
        else {
            RCLCPP_ERROR_THROTTLE(this->get_logger(), *this->get_clock(), 5000,
                "Unsupported depth encoding: %s", msg->encoding.c_str());
            return;
        }

        // Apply decimation filter on raw uint16 data
        auto start = std::chrono::high_resolution_clock::now();
        cv::Mat decimated = decimate_.apply(depth_u16);
        auto end = std::chrono::high_resolution_clock::now();
        auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end - start);
        this->decimation_cost.push_back(duration.count());

        if (this->decimation_cost.size() > 500) {
            double sum = 0;
            for (size_t i = 0; i < this->decimation_cost.size(); i++) {
                sum += this->decimation_cost[i];
            }
            double avg = sum / static_cast<double>(this->decimation_cost.size());
            RCLCPP_INFO(this->get_logger(), "Average decimation time: %f us", avg);
            double std_dev = 0;
            for (size_t i = 0; i < this->decimation_cost.size(); i++) {
                std_dev += (this->decimation_cost[i] - avg) * (this->decimation_cost[i] - avg);
            }
            std_dev = std_dev / static_cast<double>(this->decimation_cost.size());
            std_dev = std::sqrt(std_dev);
            RCLCPP_INFO(this->get_logger(), "Standard deviation of decimation time: %f us", std_dev);
        }

        const int width  = decimated.cols;
        const int height = decimated.rows;

        // Rebuild threshold matrix if image dimensions changed
        if (thresh_mat_.empty() || thresh_mat_.cols != width || thresh_mat_.rows != height)
        {
            float fov[2] = {fov_h_, fov_v_};
            thresh_mat_ = threshold_matrix_u16(
                max_obstacle_dist_raw_, drone_radius_, depth_scale_, fov, width, height);
            RCLCPP_INFO(this->get_logger(),
                "Threshold matrix built for %dx%d (FOV %.1f x %.1f deg)",
                width, height, fov_h_, fov_v_);
        }

        // Apply threshold matrix — zero out pixels beyond adaptive distance
        // Both decimated and thresh_mat_ are CV_16U, so this comparison is integer-only.
        decimated.setTo(0, decimated >= thresh_mat_);

        // ----------------------------------------------------------------
        // BFS clustering and on-the-fly metric computation
        // ----------------------------------------------------------------
        cv::Mat visited = cv::Mat::zeros(height, width, CV_8U);
        int group_id = 1;

        std::vector<int> cluster_min_x;
        std::vector<int> cluster_max_x;
        std::vector<int> cluster_min_y;
        std::vector<int> cluster_max_y;
        std::vector<uint32_t> cluster_depth_sums;  // raw-unit sums (uint32 avoids overflow)
        std::vector<int>     cluster_counts;

        std::vector<cv::Point> q;
        q.reserve(width * height);

        const uint16_t thresh_raw = depth_threshold_raw_;

        for (int y = 0; y < height; y++)
        {
            const uint16_t* depth_row = decimated.ptr<uint16_t>(y);
            uchar* visited_row = visited.ptr<uchar>(y);

            for (int x = 0; x < width; x++)
            {
                if (visited_row[x])
                    continue;

                uint16_t d = depth_row[x];
                if (d == 0)
                    continue;

                q.clear();
                q.push_back({x, y});
                visited_row[x] = 1;

                int cnt = 0;
                int mn_x = width, mx_x = 0;
                int mn_y = height, mx_y = 0;
                uint32_t depth_sum = 0;

                int head = 0;
                while (head < static_cast<int>(q.size()))
                {
                    cv::Point p = q[head++];

                    uint16_t base_depth = decimated.ptr<uint16_t>(p.y)[p.x];

                    cnt++;
                    mn_x = std::min(mn_x, p.x);
                    mx_x = std::max(mx_x, p.x);
                    mn_y = std::min(mn_y, p.y);
                    mx_y = std::max(mx_y, p.y);
                    depth_sum += base_depth;

                    static constexpr int dx[4] = {-1, 1,  0, 0};
                    static constexpr int dy[4] = { 0, 0, -1, 1};

                    for (int i = 0; i < 4; i++)
                    {
                        int nx = p.x + dx[i];
                        int ny = p.y + dy[i];

                        if (nx >= 0 && nx < width && ny >= 0 && ny < height)
                        {
                            uchar* n_vis_row = visited.ptr<uchar>(ny);
                            if (!n_vis_row[nx])
                            {
                                uint16_t nd = decimated.ptr<uint16_t>(ny)[nx];
                                if (nd == 0)
                                    continue;

                                // Integer abs diff — no float involved
                                uint16_t diff = (nd > base_depth)
                                    ? (nd - base_depth) : (base_depth - nd);
                                if (diff < thresh_raw)
                                {
                                    n_vis_row[nx] = 1;
                                    q.push_back({nx, ny});
                                }
                            }
                        }
                    }
                }

                if (cnt >= min_group_size_)
                {
                    uint16_t mean_raw = static_cast<uint16_t>(depth_sum / cnt);
                    if (mean_raw <= max_obstacle_dist_raw_)
                    {
                        cluster_min_x.push_back(mn_x);
                        cluster_max_x.push_back(mx_x);
                        cluster_min_y.push_back(mn_y);
                        cluster_max_y.push_back(mx_y);
                        cluster_depth_sums.push_back(depth_sum);
                        cluster_counts.push_back(cnt);

                        float mean_m = mean_raw * depth_scale_;
                        RCLCPP_INFO_THROTTLE(this->get_logger(), *this->get_clock(), 1000,
                            "Cluster %d: depth=%.2fm, x=[%d, %d], y=[%d, %d], pixels=%d",
                            group_id, mean_m, mn_x, mx_x, mn_y, mx_y, cnt);
                    }
                }

                group_id++;
            }
        }

        // ----------------------------------------------------------------
        // Publish obstacle_detected
        // ----------------------------------------------------------------
        const bool any_detected = !cluster_counts.empty();

        std_msgs::msg::Bool det_msg;
        det_msg.data = any_detected;
        pub_detected_->publish(det_msg);

        if (!any_detected)
            return;

        // ----------------------------------------------------------------
        // Format output as a Float32MultiArray [min_x, max_x, min_y, max_y, depth_m, ...]
        // Convert to metres only here, at publish time.
        // ----------------------------------------------------------------
        std_msgs::msg::Float32MultiArray bboxes_msg;
        for (size_t i = 0; i < cluster_counts.size(); ++i)
        {
            float depth_m = static_cast<float>(cluster_depth_sums[i]) / cluster_counts[i]
                          * depth_scale_;
            bboxes_msg.data.push_back(static_cast<float>(cluster_min_x[i]));
            bboxes_msg.data.push_back(static_cast<float>(cluster_max_x[i]));
            bboxes_msg.data.push_back(static_cast<float>(cluster_min_y[i]));
            bboxes_msg.data.push_back(static_cast<float>(cluster_max_y[i]));
            bboxes_msg.data.push_back(depth_m);
        }

        pub_bboxes_->publish(bboxes_msg);

        // ----------------------------------------------------------------
        // Compute and publish average distance across all valid clusters
        // ----------------------------------------------------------------
        uint64_t total_raw = 0;
        int total_cnt = 0;
        for (size_t i = 0; i < cluster_counts.size(); ++i)
        {
            total_raw += cluster_depth_sums[i];
            total_cnt += cluster_counts[i];
        }
        float avg_depth_m = static_cast<float>(total_raw) / total_cnt * depth_scale_;

        std_msgs::msg::Float32 dist_msg;
        dist_msg.data = avg_depth_m;
        pub_distance_->publish(dist_msg);

        RCLCPP_INFO_THROTTLE(this->get_logger(), *this->get_clock(), 1000,
            "Obstacle detected | clusters: %zu | distance: %.2fm",
            cluster_counts.size(), avg_depth_m);
    }

    /**
     * Build the per-pixel threshold matrix in raw uint16 units.
     * @param max_depth_raw  Maximum obstacle distance in raw sensor units.
     * @param radius_m       Drone radius in metres.
     * @param depth_scale    Multiplier to convert raw units → metres (e.g. 0.001).
     * @param fov            [horizontal_deg, vertical_deg]
     */
    cv::Mat threshold_matrix_u16(uint16_t max_depth_raw, float radius_m,
                                 float depth_scale, float fov[2],
                                 int width, int height)
    {
        cv::Mat thresh_mat(height, width, CV_16U);
        const float cx = width  / 2.0f;
        const float cy = height / 2.0f;
        const float hf_ppx = fov[0] * static_cast<float>(CV_PI) / 180.0f / width;
        const float vf_ppx = fov[1] * static_cast<float>(CV_PI) / 180.0f / height;
        const float inv_scale = 1.0f / depth_scale;

        for (int y = 0; y < height; y++)
        {
            uint16_t* row = thresh_mat.ptr<uint16_t>(y);
            for (int x = 0; x < width; x++)
            {
                const float sh = std::sin(hf_ppx * (x - cx));
                const float sv = std::sin(vf_ppx * (y - cy));
                const float denom = sh * sh + sv * sv;

                // Compute depth in metres, then convert to raw units
                float depth_m = (denom > 1e-12f)
                    ? radius_m / std::sqrt(denom)
                    : static_cast<float>(max_depth_raw) * depth_scale;

                uint16_t depth_raw = static_cast<uint16_t>(
                    std::min(depth_m * inv_scale,
                             static_cast<float>(max_depth_raw)));
                row[x] = depth_raw;
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
    uint16_t    depth_threshold_raw_;     // depth threshold in raw sensor units
    int         min_group_size_;
    uint16_t    max_obstacle_dist_raw_;   // max obstacle distance in raw units
    float       drone_radius_;
    cv::Mat     thresh_mat_;              // CV_16U threshold matrix in raw units

    // ----------------------------------------------------------------
    // ROS subscriber
    // ----------------------------------------------------------------
    rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr depth_sub_;

    // ----------------------------------------------------------------
    // Publishers
    // ----------------------------------------------------------------
    rclcpp::Publisher<std_msgs::msg::Bool>::SharedPtr    pub_detected_;
    rclcpp::Publisher<std_msgs::msg::Float32>::SharedPtr pub_distance_;
    rclcpp::Publisher<std_msgs::msg::Float32MultiArray>::SharedPtr pub_bboxes_;
};

int main(int argc, char ** argv)
{
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<DepthClusterNode>());
    rclcpp::shutdown();
    return 0;
}
