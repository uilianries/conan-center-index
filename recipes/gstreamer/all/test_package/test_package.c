#include <stdlib.h>
#include <stdio.h>
#include <gst/gst.h>

#ifdef GST_STATIC_COMPILATION
GST_PLUGIN_STATIC_DECLARE(coreelements);
#endif

/* VA elements are provided by gst-plugins-bad (libgstva). Names vary slightly by version. */
static void try_exercise_libva_gst_plugin(void)
{
    static const char *const va_element_names[] = {
        "vah264dec",
        "vah265dec",
        "vaav1dec",
        "vaapih264dec",
        "vaapisink",
        NULL,
    };

    for (size_t i = 0; va_element_names[i] != NULL; ++i) {
        GstElementFactory *factory = gst_element_factory_find(va_element_names[i]);
        if (!factory) {
            continue;
        }
        printf("VA plugin: found factory \"%s\"\n", va_element_names[i]);
        GstElement *el = gst_element_factory_create(factory, NULL);
        gst_object_unref(factory);
        if (el) {
            printf("VA plugin: created element \"%s\" successfully\n", va_element_names[i]);
            gst_object_unref(GST_OBJECT(el));
        } else {
            printf("VA plugin: factory \"%s\" found but element creation failed "
                   "(often no usable VA display/driver in this environment)\n",
                   va_element_names[i]);
        }
        return;
    }
    printf("VA plugin: no VA element factories found "
           "(build/install gst-plugins-bad with libva and set GST_PLUGIN_PATH)\n");
}

int main(int argc, char * argv[])
{
    gst_init(&argc, &argv);
    printf("GStreamer version: %s\n", gst_version_string());

#ifdef GST_STATIC_COMPILATION
    GST_PLUGIN_STATIC_REGISTER(coreelements);
#endif

    GstElement * fakesink = gst_element_factory_make("fakesink", NULL);
    if (!fakesink) {
        printf("failed to create fakesink element\n");
        return EXIT_FAILURE;
    } else {
        printf("fakesink has been created successfully\n");
    }
    gst_object_unref(GST_OBJECT(fakesink));
    GstElement * fakesrc = gst_element_factory_make("fakesrc", NULL);
    if (!fakesrc) {
        printf("failed to create fakesrc element\n");
        return EXIT_FAILURE;
    } else {
        printf("fakesrc has been created successfully\n");
    }
    gst_object_unref(GST_OBJECT(fakesrc));

    try_exercise_libva_gst_plugin();

    return EXIT_SUCCESS;
}
