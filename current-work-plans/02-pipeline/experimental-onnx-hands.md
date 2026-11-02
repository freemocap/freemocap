# Experimental ONNX hands

The realtime preset `rtmw_onnx_hands` is available for explicit comparison and is
labeled experimental in the application. It reuses Tracker's recipe and crop
transport; it does not replace the supported RTMW + MediaPipe hands preset or
add a posthoc selection.

Live visual acceptance failed. The current candidate must not be described as
production-ready or as an accepted quality replacement. CPU integration checks
establish preset selection and transport wiring, not hand accuracy. Retain the
existing hybrid route for accepted use while the experiment is investigated.

Recorded comparison and benchmark tests are opt-in and require prepared
recordings and pinned candidate assets. GPU benchmarks also require a separately
coordinated exclusive slot; ordinary integration tests must not allocate inference
sessions merely because this preset is listed.
