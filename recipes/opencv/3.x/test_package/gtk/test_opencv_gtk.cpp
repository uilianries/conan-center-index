#include <gtk/gtk.h>
#include <opencv2/opencv.hpp>
#include <vector>

using namespace cv;

// Global Demo State
Mat image;
RNG rng(0xFFFFFFFF);
GtkWidget *gtk_image_widget;
int draw_step = 0;

const int NUMBER = 100;
const int img_width = 1000, img_height = 700;
const int lineType = LINE_AA;

// Renamed to avoid math.h Bessel function collisions
const int c_x1 = -img_width/2, c_x2 = img_width*3/2;
const int c_y1 = -img_height/2, c_y2 = img_height*3/2;

static Scalar randomColor(RNG& rng) {
    int icolor = (unsigned)rng;
    return Scalar(icolor & 255, (icolor >> 8) & 255, (icolor >> 16) & 255);
}

// Helper to convert Mat to GdkPixbuf
GdkPixbuf* mat_to_pixbuf(Mat &frame) {
    Mat rgb;
    cvtColor(frame, rgb, COLOR_BGR2RGB);
    return gdk_pixbuf_new_from_data(
        rgb.data, GDK_COLORSPACE_RGB, FALSE, 8,
        rgb.cols, rgb.rows, (int)rgb.step, NULL, NULL);
}

gboolean update_drawing(gpointer data) {
    // 1. Lines and Arrows
    if (draw_step < NUMBER * 2) {
        Point p1(rng.uniform(c_x1, c_x2), rng.uniform(c_y1, c_y2));
        Point p2(rng.uniform(c_x1, c_x2), rng.uniform(c_y1, c_y2));
        if (rng.uniform(0, 6) < 3)
            line(image, p1, p2, randomColor(rng), rng.uniform(1, 10), lineType);
        else
            arrowedLine(image, p1, p2, randomColor(rng), rng.uniform(1, 10), lineType);
    }
    // 2. Rectangles and Markers
    else if (draw_step < NUMBER * 4) {
        Point p1(rng.uniform(c_x1, c_x2), rng.uniform(c_y1, c_y2));
        Point p2(rng.uniform(c_x1, c_x2), rng.uniform(c_y1, c_y2));
        if (rng.uniform(0, 10) > 5)
            rectangle(image, p1, p2, randomColor(rng), MAX(rng.uniform(-3, 10), -1), lineType);
        else
            drawMarker(image, p1, randomColor(rng), rng.uniform(0, 10), rng.uniform(30, 80));
    }
    // 3. Ellipses
    else if (draw_step < NUMBER * 5) {
        Point center(rng.uniform(c_x1, c_x2), rng.uniform(c_y1, c_y2));
        Size axes(rng.uniform(0, 200), rng.uniform(0, 200));
        double angle = rng.uniform(0, 180);
        ellipse(image, center, axes, angle, angle - 100, angle + 200,
                randomColor(rng), rng.uniform(-1, 9), lineType);
    }
    // 4. Text Rendering
    else if (draw_step < NUMBER * 6) {
        Point org(rng.uniform(c_x1, c_x2), rng.uniform(c_y1, c_y2));
        putText(image, "ConanRocks", org, rng.uniform(0, 8),
                rng.uniform(0, 100) * 0.05 + 0.1, randomColor(rng), rng.uniform(1, 10), lineType);
    }

    // Refresh GTK Image Widget
    GdkPixbuf *pixbuf = mat_to_pixbuf(image);
    gtk_image_set_from_pixbuf(GTK_IMAGE(gtk_image_widget), pixbuf);
    g_object_unref(pixbuf);

    draw_step++;
    return (draw_step < NUMBER * 6); // Stop timer when done
}

int main(int argc, char *argv[]) {
    gtk_init(&argc, &argv);

    image = Mat::zeros(img_height, img_width, CV_8UC3);

    GtkWidget *window = gtk_window_new(GTK_WINDOW_TOPLEVEL);
    gtk_window_set_title(GTK_WINDOW(window), "OpenCV-3.x + GTK-3 Integration");
    gtk_window_set_default_size(GTK_WINDOW(window), img_width, img_height);
    g_signal_connect(window, "destroy", G_CALLBACK(gtk_main_quit), NULL);

    gtk_image_widget = gtk_image_new();
    gtk_container_add(GTK_CONTAINER(window), gtk_image_widget);

    // Call update_drawing every 16ms (~60fps)
    g_timeout_add(16, update_drawing, NULL);

    gtk_widget_show_all(window);
    gtk_main();

    return 0;
}