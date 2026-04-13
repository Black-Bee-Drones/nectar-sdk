/**
 * depth_cluster_uf.cpp
 *
 * ROS2 node for Union-Find-based depth clustering obstacle detection.
 *
 * Same interface as depth_cluster_node (BFS version) but uses a scanline
 * union-find algorithm for connected-component labelling.  Two row-major
 * passes replace the BFS flood:
 *
 *   Pass 1 — merge depth-similar adjacent pixels (left + above neighbours).
 *   Pass 2 — collect per-cluster stats, filter by size and distance.
 *
 * Because the image is scanned in storage order the algorithm is
 * cache-friendly, which matters on constrained platforms (RPi4).
 *
 * The threshold matrix / seed mask used by the BFS version is not needed
 * here — filtering is done post-hoc on the complete clusters.
 *
 * Publishes obstacle information on:
 *   /<namespace>/obstacle_detected  (std_msgs/Bool)
 *   /<namespace>/obstacle_distance  (std_msgs/Float32)   — metres
 *   /<namespace>/obstacle_bboxes    (std_msgs/Float32MultiArray)
 *
 * Parameters (ROS2):
 *   namespace            (string,  default "obstacle_detection")
 *   depth_topic          (string,  default "/camera/camera/depth/image_rect_raw")
 *   depth_scale          (double,  default 0.001)
 *   decimation_scale     (int,     default 2)
 *   depth_threshold      (double,  default 0.06)   — max depth delta (m) to merge
 *   min_group_size       (int,     default 300)
 *   max_obstacle_distance(double,  default 1.0)
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
#include <cstring>
#include <string>
#include <vector>
#include <unordered_map>
#include <chrono>

class DepthClusterUFNode : public rclcpp::Node
{
public:
    DepthClusterUFNode()
    : Node("depth_cluster_uf_node")
    {
        // Parameters
        this->declare_parameter<std::string>("namespace", "obstacle_detection");
        this->declare_parameter<std::string>("depth_topic", "/camera/camera/depth/image_rect_raw");
        this->declare_parameter<double>("depth_scale", 0.001);
        this->declare_parameter<int>("decimation_scale", 2);
        this->declare_parameter<double>("depth_threshold", 0.06);
        this->declare_parameter<int>("min_group_size", 300);
        this->declare_parameter<double>("max_obstacle_distance", 1.0);

        ns_          = this->get_parameter("namespace").as_string();
        depth_topic_ = this->get_parameter("depth_topic").as_string();
        depth_scale_ = static_cast<float>(this->get_parameter("depth_scale").as_double());
        min_group_size_ = this->get_parameter("min_group_size").as_int();

        const float inv_scale = 1.0f / depth_scale_;
        depth_threshold_raw_ = static_cast<uint16_t>(
            this->get_parameter("depth_threshold").as_double() * inv_scale);
        max_obstacle_dist_raw_ = static_cast<uint16_t>(
            this->get_parameter("max_obstacle_distance").as_double() * inv_scale);

        int dec_scale = this->get_parameter("decimation_scale").as_int();
        decimate_ = nectar::DepthDecimationFilter(dec_scale);

        // Publishers
        pub_detected_ = this->create_publisher<std_msgs::msg::Bool>(
            "/" + ns_ + "/obstacle_detected", 10);
        pub_distance_ = this->create_publisher<std_msgs::msg::Float32>(
            "/" + ns_ + "/obstacle_distance", 10);
        pub_bboxes_ = this->create_publisher<std_msgs::msg::Float32MultiArray>(
            "/" + ns_ + "/obstacle_bboxes", 10);

        // Subscriber
        depth_sub_ = this->create_subscription<sensor_msgs::msg::Image>(
            depth_topic_, 10,
            std::bind(&DepthClusterUFNode::depth_callback, this, std::placeholders::_1));

        RCLCPP_INFO(this->get_logger(),
            "DepthClusterUFNode started — subscribing to %s, publishing on /%s/*",
            depth_topic_.c_str(), ns_.c_str());
    }

private:
    // -----------------------------------------------------------------
    // Union-Find with path compression and union by rank
    // -----------------------------------------------------------------
    int uf_find(int x)
    {
        while (parent_[x] != x)
        {
            parent_[x] = parent_[parent_[x]];   // path splitting
            x = parent_[x];
        }
        return x;
    }

    void uf_unite(int a, int b)
    {
        a = uf_find(a);
        b = uf_find(b);
        if (a == b) return;
        if (rank_[a] < rank_[b]) std::swap(a, b);
        parent_[b] = a;
        if (rank_[a] == rank_[b]) rank_[a]++;
    }

    // -----------------------------------------------------------------
    // Depth callback
    // -----------------------------------------------------------------
    void depth_callback(const sensor_msgs::msg::Image::ConstSharedPtr& msg)
    {
        auto t0 = std::chrono::high_resolution_clock::now();

        // Convert ROS Image → cv::Mat
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

        cv::Mat depth_u16;
        if (depth_raw.type() == CV_16U) {
            depth_u16 = depth_raw;
        } else if (depth_raw.type() == CV_32F) {
            depth_raw.convertTo(depth_u16, CV_16U, 1.0 / depth_scale_);
        } else {
            RCLCPP_ERROR_THROTTLE(this->get_logger(), *this->get_clock(), 5000,
                "Unsupported depth encoding: %s", msg->encoding.c_str());
            return;
        }

        cv::Mat decimated = decimate_.apply(depth_u16);

        const int width  = decimated.cols;
        const int height = decimated.rows;
        const int npix   = width * height;

        // Ensure UF arrays are large enough (allocated once, reused)
        if (static_cast<int>(parent_.size()) != npix)
        {
            parent_.resize(npix);
            rank_.resize(npix);
        }

        // Flat pointer to contiguous image data
        const uint16_t* depth = decimated.ptr<uint16_t>(0);
        const uint16_t thresh_raw = depth_threshold_raw_;

        // Initialise parent to -1 (invalid); valid pixels set themselves
        std::memset(parent_.data(), -1, npix * sizeof(int));
        std::memset(rank_.data(), 0, npix * sizeof(int));

        // =============================================================
        // Pass 1 — Label & Merge (row-major scan, 2 neighbours)
        // =============================================================
        for (int y = 0; y < height; y++)
        {
            const int row = y * width;
            for (int x = 0; x < width; x++)
            {
                const int idx = row + x;
                const uint16_t d = depth[idx];
                if (d == 0) continue;          // invalid pixel

                parent_[idx] = idx;            // new singleton set

                // LEFT neighbour
                if (x > 0)
                {
                    const int left = idx - 1;
                    if (depth[left] != 0)
                    {
                        uint16_t diff = (d > depth[left])
                            ? (d - depth[left]) : (depth[left] - d);
                        if (diff < thresh_raw)
                            uf_unite(idx, left);
                    }
                }

                // ABOVE neighbour
                if (y > 0)
                {
                    const int above = idx - width;
                    if (depth[above] != 0)
                    {
                        uint16_t diff = (d > depth[above])
                            ? (d - depth[above]) : (depth[above] - d);
                        if (diff < thresh_raw)
                            uf_unite(idx, above);
                    }
                }
            }
        }

        // =============================================================
        // Pass 2 — Collect per-cluster statistics
        // =============================================================
        struct ClusterStats
        {
            int min_x;
            int max_x;
            int min_y;
            int max_y;
            uint32_t depth_sum;
            int count;
        };

        std::unordered_map<int, ClusterStats> clusters;
        clusters.reserve(256);

        for (int y = 0; y < height; y++)
        {
            const int row = y * width;
            for (int x = 0; x < width; x++)
            {
                const int idx = row + x;
                if (depth[idx] == 0) continue;

                int root = uf_find(idx);

                auto it = clusters.find(root);
                if (it == clusters.end())
                {
                    clusters[root] = {x, x, y, y, depth[idx], 1};
                }
                else
                {
                    ClusterStats& s = it->second;
                    if (x < s.min_x) s.min_x = x;
                    if (x > s.max_x) s.max_x = x;
                    if (y < s.min_y) s.min_y = y;
                    if (y > s.max_y) s.max_y = y;
                    s.depth_sum += depth[idx];
                    s.count++;
                }
            }
        }

        // =============================================================
        // Filter clusters and build output
        // =============================================================
        std::vector<float> bbox_data;
        uint64_t total_raw = 0;
        int total_cnt = 0;
        int cluster_id = 0;

        for (auto& [root, s] : clusters)
        {
            if (s.count < min_group_size_) continue;

            uint16_t mean_raw = static_cast<uint16_t>(s.depth_sum / s.count);
            if (mean_raw > max_obstacle_dist_raw_) continue;

            bbox_data.push_back(static_cast<float>(s.min_x));
            bbox_data.push_back(static_cast<float>(s.max_x));
            bbox_data.push_back(static_cast<float>(s.min_y));
            bbox_data.push_back(static_cast<float>(s.max_y));
            bbox_data.push_back(static_cast<float>(s.depth_sum) / s.count * depth_scale_);

            total_raw += s.depth_sum;
            total_cnt += s.count;

            float mean_m = mean_raw * depth_scale_;
            RCLCPP_INFO_THROTTLE(this->get_logger(), *this->get_clock(), 1000,
                "Cluster %d: depth=%.2fm, x=[%d, %d], y=[%d, %d], pixels=%d",
                cluster_id, mean_m, s.min_x, s.max_x, s.min_y, s.max_y, s.count);
            cluster_id++;
        }

        // Publish obstacle_detected
        std_msgs::msg::Bool det_msg;
        det_msg.data = !bbox_data.empty();
        pub_detected_->publish(det_msg);

        if (bbox_data.empty())
        {
            // Metrics even when no obstacle
            record_frame_time(t0);
            return;
        }

        // Publish bboxes
        std_msgs::msg::Float32MultiArray bboxes_msg;
        bboxes_msg.data = std::move(bbox_data);
        pub_bboxes_->publish(bboxes_msg);

        // Publish average distance
        float avg_depth_m = static_cast<float>(total_raw) / total_cnt * depth_scale_;
        std_msgs::msg::Float32 dist_msg;
        dist_msg.data = avg_depth_m;
        pub_distance_->publish(dist_msg);

        RCLCPP_INFO_THROTTLE(this->get_logger(), *this->get_clock(), 1000,
            "Obstacle detected | clusters: %d | distance: %.2fm",
            cluster_id, avg_depth_m);

        record_frame_time(t0);
    }

    // -----------------------------------------------------------------
    // Frame timing metrics
    // -----------------------------------------------------------------
    static constexpr size_t kMetricWindow = 1000;

    void record_frame_time(std::chrono::high_resolution_clock::time_point t0)
    {
        auto t1 = std::chrono::high_resolution_clock::now();
        double us = std::chrono::duration<double, std::micro>(t1 - t0).count();
        frame_times_.push_back(us);

        if (frame_times_.size() >= kMetricWindow)
        {
            double sum = 0.0, sq_sum = 0.0;
            for (double t : frame_times_) { sum += t; sq_sum += t * t; }
            double avg = sum / kMetricWindow;
            double std_dev = std::sqrt(sq_sum / kMetricWindow - avg * avg);
            RCLCPP_INFO(this->get_logger(),
                "Frame time (%zu frames): avg=%.1f us, std=%.1f us",
                kMetricWindow, avg, std_dev);
            frame_times_.clear();
        }
    }

    // -----------------------------------------------------------------
    // Members
    // -----------------------------------------------------------------
    nectar::DepthDecimationFilter decimate_;

    std::string ns_;
    std::string depth_topic_;
    float       depth_scale_{0.001f};
    uint16_t    depth_threshold_raw_;
    int         min_group_size_;
    uint16_t    max_obstacle_dist_raw_;

    // Union-Find arrays (reused across frames)
    std::vector<int> parent_;
    std::vector<int> rank_;

    // Metrics
    std::vector<double> frame_times_;

    // ROS
    rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr depth_sub_;
    rclcpp::Publisher<std_msgs::msg::Bool>::SharedPtr         pub_detected_;
    rclcpp::Publisher<std_msgs::msg::Float32>::SharedPtr      pub_distance_;
    rclcpp::Publisher<std_msgs::msg::Float32MultiArray>::SharedPtr pub_bboxes_;
};

int main(int argc, char** argv)
{
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<DepthClusterUFNode>());
    rclcpp::shutdown();
    return 0;
}
