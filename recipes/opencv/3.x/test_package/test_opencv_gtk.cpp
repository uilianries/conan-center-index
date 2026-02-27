#include <gtk/gtk.h>
#include <glib.h>
#include <opencv/cv.h>
#include <opencv/cxcore.h>

#include <stdio.h>

gint t = 0;
IplImage* opencvImage;
GdkPixbuf* pix;

gboolean
expose_event_callback(GtkWidget *widget, GdkEventExpose *event, gpointer data)
{

  pix = gdk_pixbuf_new_from_data((guchar*) opencvImage->imageData,
      GDK_COLORSPACE_RGB, FALSE, opencvImage->depth, opencvImage->width,
      opencvImage->height, (opencvImage->widthStep), NULL, NULL);

  gdk_draw_pixbuf(widget->window,
      widget->style->fg_gc[GTK_WIDGET_STATE (widget)], pix, 0, 0, 0, 0,
      opencvImage->width, opencvImage->height, GDK_RGB_DITHER_NONE, 0, 0); /* Other possible values are  GDK_RGB_DITHER_MAX,  GDK_RGB_DITHER_NORMAL */

  return TRUE;
}

int
main(int argc, char *argv[])
{
    int height,width,step,channels;
  uchar *data;
  int i,j,k;

  GtkWidget *window;
  GtkWidget *drawing_area;
  gtk_init (&argc, &argv);

//Change this path in order to load any other image.
  opencvImage = cvLoadImage("recharge.JPG", 1);


  // get the image data
  height    = opencvImage->height;
  width     = opencvImage->width;
  step      = opencvImage->widthStep;
  channels  = opencvImage->nChannels;
  data      = (uchar *)opencvImage->imageData;

  // invert the image
  for(i=0;i<height;i++) for(j=0;j<width;j++) for(k=0;k<channels;k++)
    data[i*step+j*channels+k]=255-data[i*step+j*channels+k];


  cvCvtColor(opencvImage, opencvImage, CV_BGR2RGB);

  window = gtk_window_new(GTK_WINDOW_TOPLEVEL);

  gtk_window_set_title(GTK_WINDOW (window), "RESET DEMO");
  g_signal_connect (G_OBJECT (window), "destroy",
      G_CALLBACK (gtk_main_quit), NULL);

  /* Now add a child widget to the aspect frame */
  drawing_area = gtk_drawing_area_new();

  /* Ask for a 200x200 window, but the AspectFrame will give us a 200x100
   * window since we are forcing a 2x1 aspect ratio */
  gtk_widget_set_size_request(drawing_area, opencvImage->width, opencvImage->height);
  gtk_container_add(GTK_CONTAINER (window), drawing_area);
  gtk_widget_show(drawing_area);

  g_signal_connect (G_OBJECT (drawing_area), "expose_event",
      G_CALLBACK (expose_event_callback), NULL);

  gtk_widget_show(window);
  gtk_main();
  return 0;
}