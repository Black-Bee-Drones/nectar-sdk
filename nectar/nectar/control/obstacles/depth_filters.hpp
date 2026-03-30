/**
 * depth_filters.hpp
 *
 * OpenCV-based depth post-processing filters, re-implementing the relevant
 * algorithms from the Intel RealSense SDK (librealsense2) so that they can
 * operate on plain cv::Mat depth images received from ROS topics.
 *
 * Reference:  librealsense2/src/proc/decimation-filter.cpp
 *             (Apache-2.0, Copyright (c) 2017 Intel Corporation)
 *
 * Currently implements:
 *   - DepthDecimationFilter  (median-based depth downsampling)
 */

#pragma once

#include <algorithm>
#include <cstdint>

#include <opencv2/core.hpp>

namespace nectar {

// ============================================================================
//  Helpers — optimized median selection (sorting-network based)
//  Ported from librealsense2  src/proc/decimation-filter.cpp
// ============================================================================

namespace detail {

#define NECTAR_PIX_SORT(a, b) \
    do {                      \
        if ((a) > (b))        \
            std::swap(a, b);  \
    } while (0)

template <typename T>
inline T pix_min(T a, T b) { return (a < b) ? a : b; }

template <typename T>
inline T pix_max(T a, T b) { return (a > b) ? a : b; }

template <typename T>
inline T opt_med3(T* p)
{
    NECTAR_PIX_SORT(p[0], p[1]);
    NECTAR_PIX_SORT(p[1], p[2]);
    NECTAR_PIX_SORT(p[0], p[1]);
    return p[1];
}

template <typename T>
inline T opt_med4(T* p)
{
    NECTAR_PIX_SORT(p[0], p[1]);
    NECTAR_PIX_SORT(p[2], p[3]);
    NECTAR_PIX_SORT(p[0], p[2]);
    NECTAR_PIX_SORT(p[1], p[3]);
    return pix_min(p[1], p[2]);
}

template <typename T>
inline T opt_med5(T* p)
{
    NECTAR_PIX_SORT(p[0], p[1]);
    NECTAR_PIX_SORT(p[3], p[4]);
    p[3] = pix_max(p[0], p[3]);
    p[1] = pix_min(p[1], p[4]);
    NECTAR_PIX_SORT(p[1], p[2]);
    p[2] = pix_min(p[2], p[3]);
    return pix_max(p[1], p[2]);
}

template <typename T>
inline T opt_med6(T* p)
{
    NECTAR_PIX_SORT(p[1], p[2]);
    NECTAR_PIX_SORT(p[3], p[4]);
    NECTAR_PIX_SORT(p[0], p[1]);
    NECTAR_PIX_SORT(p[2], p[3]);
    NECTAR_PIX_SORT(p[4], p[5]);
    NECTAR_PIX_SORT(p[1], p[2]);
    NECTAR_PIX_SORT(p[3], p[4]);
    NECTAR_PIX_SORT(p[0], p[1]);
    NECTAR_PIX_SORT(p[2], p[3]);
    p[4] = pix_min(p[4], p[5]);
    p[2] = pix_max(p[1], p[2]);
    p[3] = pix_min(p[3], p[4]);
    return pix_min(p[2], p[3]);
}

template <typename T>
inline T opt_med7(T* p)
{
    NECTAR_PIX_SORT(p[0], p[5]);
    NECTAR_PIX_SORT(p[0], p[3]);
    NECTAR_PIX_SORT(p[1], p[6]);
    NECTAR_PIX_SORT(p[2], p[4]);
    NECTAR_PIX_SORT(p[0], p[1]);
    NECTAR_PIX_SORT(p[3], p[5]);
    NECTAR_PIX_SORT(p[2], p[6]);
    p[3] = pix_max(p[2], p[3]);
    p[3] = pix_min(p[3], p[6]);
    p[4] = pix_min(p[4], p[5]);
    NECTAR_PIX_SORT(p[1], p[4]);
    p[3] = pix_max(p[1], p[3]);
    return pix_min(p[3], p[4]);
}

template <typename T>
inline T opt_med8(T* p)
{
    NECTAR_PIX_SORT(p[0], p[1]);
    NECTAR_PIX_SORT(p[3], p[4]);
    NECTAR_PIX_SORT(p[6], p[7]);
    NECTAR_PIX_SORT(p[2], p[3]);
    NECTAR_PIX_SORT(p[5], p[6]);
    NECTAR_PIX_SORT(p[3], p[4]);
    NECTAR_PIX_SORT(p[6], p[7]);
    p[4] = pix_min(p[4], p[7]);
    NECTAR_PIX_SORT(p[3], p[6]);
    p[5] = pix_max(p[2], p[5]);
    p[3] = pix_max(p[0], p[3]);
    p[1] = pix_min(p[1], p[4]);
    p[3] = pix_min(p[3], p[6]);
    NECTAR_PIX_SORT(p[3], p[1]);
    p[3] = pix_max(p[5], p[3]);
    return pix_min(p[3], p[1]);
}

template <typename T>
inline T opt_med9(T* p)
{
    NECTAR_PIX_SORT(p[1], p[2]);
    NECTAR_PIX_SORT(p[4], p[5]);
    NECTAR_PIX_SORT(p[7], p[8]);
    NECTAR_PIX_SORT(p[0], p[1]);
    NECTAR_PIX_SORT(p[3], p[4]);
    NECTAR_PIX_SORT(p[6], p[7]);
    NECTAR_PIX_SORT(p[1], p[2]);
    NECTAR_PIX_SORT(p[4], p[5]);
    NECTAR_PIX_SORT(p[7], p[8]);
    p[3] = pix_max(p[0], p[3]);
    p[5] = pix_min(p[5], p[8]);
    NECTAR_PIX_SORT(p[4], p[7]);
    p[6] = pix_max(p[3], p[6]);
    p[4] = pix_max(p[1], p[4]);
    p[2] = pix_min(p[2], p[5]);
    p[4] = pix_min(p[4], p[7]);
    NECTAR_PIX_SORT(p[4], p[2]);
    p[4] = pix_max(p[6], p[4]);
    return pix_min(p[4], p[2]);
}

#undef NECTAR_PIX_SORT

/**
 * Select the median from a kernel buffer of `count` valid elements.
 * Uses the optimized sorting-network routines for count <= 9,
 * falls back to std::nth_element for larger kernels.
 */
template <typename T>
inline T select_median(T* buf, int count)
{
    switch (count)
    {
    case 0:  return T(0);
    case 1:  return buf[0];
    case 2:  return std::min(buf[0], buf[1]);
    case 3:  return opt_med3(buf);
    case 4:  return opt_med4(buf);
    case 5:  return opt_med5(buf);
    case 6:  return opt_med6(buf);
    case 7:  return opt_med7(buf);
    case 8:  return opt_med8(buf);
    case 9:  return opt_med9(buf);
    default:
    {
        int mid = count / 2;
        std::nth_element(buf, buf + mid, buf + count);
        return buf[mid];
    }
    }
}

} // namespace detail

// ============================================================================
//  DepthDecimationFilter
// ============================================================================

/**
 * Downsample a depth image by a factor of N using median selection.
 *
 * This reproduces the behaviour of rs2::decimation_filter:
 *   - For scale 2–3: median of non-zero values in each NxN patch
 *   - For scale >= 4: mean of non-zero values (same as Intel fallback)
 *   - Zero (invalid) pixels are excluded from the computation
 *   - If all pixels in a patch are zero, the output pixel is zero
 *
 * Accepts CV_16U (raw Z16) or CV_32F (metres).
 */
class DepthDecimationFilter
{
public:
    /**
     * @param scale  Decimation factor (1–8).  1 = passthrough.
     */
    explicit DepthDecimationFilter(int scale = 2)
        : scale_(std::max(1, std::min(8, scale)))
    {}

    void set_scale(int s) { scale_ = std::max(1, std::min(8, s)); }
    int  get_scale() const { return scale_; }

    /**
     * Apply the decimation filter.
     *
     * @param src  Input depth image (CV_16U or CV_32F).
     * @return     Decimated depth image of the same type,
     *             with dimensions  floor(src.cols/scale) x floor(src.rows/scale).
     */
    cv::Mat apply(const cv::Mat& src) const
    {
        if (scale_ <= 1)
            return src.clone();

        if (src.type() == CV_16U)
            return decimate<uint16_t>(src);
        else if (src.type() == CV_32F)
            return decimate<float>(src);
        else
        {
            // Unsupported type — return a copy unchanged
            return src.clone();
        }
    }

private:
    int scale_;

    template <typename T>
    cv::Mat decimate(const cv::Mat& src) const
    {
        // Local copy — lets the compiler keep it in a register
        // instead of reloading the member through `this` each iteration.
        const int scale = scale_;

        const int out_w = src.cols / scale;
        const int out_h = src.rows / scale;

        cv::Mat dst(out_h, out_w, src.type(), cv::Scalar(0));

        // For scales 2–3 use median; for >= 4 use mean (matching Intel behaviour).
        // Branch is hoisted outside the pixel loops entirely.
        if (scale <= 3)
        {
            // ---------- median path (scale 2–3) ----------
            for (int oy = 0; oy < out_h; ++oy)
            {
                // Pre-compute row pointers for the N source rows of this patch-row.
                const T* row_ptrs[8]; // max scale = 8
                const int by = oy * scale;
                for (int dy = 0; dy < scale; ++dy)
                    row_ptrs[dy] = src.ptr<T>(by + dy);

                T* dst_ptr = dst.ptr<T>(oy);
                T kernel_buf[64]; // max 8×8

                for (int ox = 0, bx = 0; ox < out_w; ++ox, bx += scale)
                {
                    int valid = 0;

                    for (int dy = 0; dy < scale; ++dy)
                    {
                        const T* p = row_ptrs[dy] + bx;
                        for (int dx = 0; dx < scale; ++dx)
                        {
                            if (p[dx] != T(0))
                                kernel_buf[valid++] = p[dx];
                        }
                    }

                    *dst_ptr++ = (valid == 0)
                        ? T(0)
                        : detail::select_median(kernel_buf, valid);
                }
            }
        }
        else
        {
            // ---------- mean path (scale >= 4) ----------
            for (int oy = 0; oy < out_h; ++oy)
            {
                const T* row_ptrs[8];
                const int by = oy * scale;
                for (int dy = 0; dy < scale; ++dy)
                    row_ptrs[dy] = src.ptr<T>(by + dy);

                T* dst_ptr = dst.ptr<T>(oy);

                for (int ox = 0, bx = 0; ox < out_w; ++ox, bx += scale)
                {
                    double sum = 0.0;
                    int valid = 0;

                    for (int dy = 0; dy < scale; ++dy)
                    {
                        const T* p = row_ptrs[dy] + bx;
                        for (int dx = 0; dx < scale; ++dx)
                        {
                            if (p[dx] != T(0))
                            {
                                sum += static_cast<double>(p[dx]);
                                ++valid;
                            }
                        }
                    }

                    *dst_ptr++ = (valid == 0)
                        ? T(0)
                        : static_cast<T>(sum / valid);
                }
            }
        }

        return dst;
    }
};

} // namespace nectar
