#include <gtk/gtk.h>
#include <opencv2/core.hpp>
#include <opencv2/imgproc.hpp>
#include <stdio.h>

using namespace cv;

// Global structure to hold our GUI state
struct AppData {
    GtkWidget *image_widget;
    Mat image;
    RNG rng;
    int width, height;
    int x1, x2, y1, y2;
    int lineType;
};

// Helper to convert OpenCV Mat (BGR) to GTK GdkPixbuf (RGB)
GdkPixbuf* mat_to_pixbuf(const Mat& mat) {
    Mat rgb;
    cvtColor(mat, rgb, COLOR_BGR2RGB); // GTK needs RGB
    return gdk_pixbuf_new_from_data(
        rgb.data, GDK_COLORSPACE_RGB, FALSE, 8,
        rgb.cols, rgb.rows, rgb.step, NULL, NULL);
}

// Function to refresh the UI with the latest Mat data
void update_ui(AppData* data) {
    GdkPixbuf* pixbuf = mat_to_pixbuf(data->image);
    gtk_image_set_from_pixbuf(GTK_IMAGE(data->image_widget), pixbuf);
    g_object_unref(pixbuf);

    // Process pending events to keep UI responsive
    while (gtk_events_pending()) gtk_main_iteration();
}

static Scalar randomColor(RNG& rng) {
    int icolor = (unsigned)rng;
    return Scalar(icolor&255, (icolor>>8)&255, (icolor>>16)&255);
}

// Timer callback that handles the drawing logic (replacing the for-loops)
static gboolean on_draw_timer(gpointer user_data) {
    AppData* data = (AppData*)user_data;
    static int stage = 0;
    static int i = 0;
    const int NUMBER = 100;

    // Stage 1: Lines & Arrows
    if (stage == 0) {
        Point pt1(data->rng.uniform(data->x1, data->x2), data->rng.uniform(data->y1, data->y2));
        Point pt2(data->rng.uniform(data->x1, data->x2), data->rng.uniform(data->y1, data->y2));
        if (data->rng.uniform(0, 6) < 3)
            line(data->image, pt1, pt2, randomColor(data->rng), data->rng.uniform(1,10), data->lineType);
        else
            arrowedLine(data->image, pt1, pt2, randomColor(data->rng), data->rng.uniform(1, 10), data->lineType);

        if (++i >= NUMBER * 2) { i = 0; stage++; }
    }
    // Stage 2: Rectangles & Markers
    else if (stage == 1) {
        Point pt1(data->rng.uniform(data->x1, data->x2), data->rng.uniform(data->y1, data->y2));
        Point pt2(data->rng.uniform(data->x1, data->x2), data->rng.uniform(data->y1, data->y2));
        if (data->rng.uniform(0, 10) > 5)
            rectangle(data->image, pt1, pt2, randomColor(data->rng), MAX(data->rng.uniform(-3, 10), -1), data->lineType);
        else
            drawMarker(data->image, pt1, randomColor(data->rng), data->rng.uniform(0, 10), data->rng.uniform(30, 80));

        if (++i >= NUMBER * 2) { i = 0; stage++; }
    }
    // (Additional stages like Ellipses, Circles, Text can be added here following the same pattern)

    update_ui(data);
    return (stage < 2); // Return FALSE to stop the timer
}

int main(int argc, char** argv) {
    gtk_init(&argc, &argv);

    AppData data;
    data.width = 1000; data.height = 700;
    data.x1 = -data.width/2; data.x2 = data.width*3/2;
    data.y1 = -data.height/2; data.y2 = data.height*3/2;
    data.lineType = LINE_AA;
    data.rng = RNG(0xFFFFFFFF);
    data.image = Mat::zeros(data.height, data.width, CV_8UC3);

    // GTK Window Setup
    GtkWidget *window = gtk_window_new(GTK_WINDOW_TOPLEVEL);
    gtk_window_set_title(GTK_WINDOW(window), "Conan - OpenCV-4 + GTK3");
    g_signal_connect(window, "destroy", G_CALLBACK(gtk_main_quit), NULL);

    data.image_widget = gtk_image_new();
    gtk_container_add(GTK_CONTAINER(window), data.image_widget);

    gtk_widget_show_all(window);

    // Start drawing loop using a GLib timeout (5ms)
    g_timeout_add(5, on_draw_timer, &data);

    gtk_main();
    return 0;
}