# VMC receiver bindings

The default `vrm0_normalized` binding targets normalized VRM0 T-pose axes, as
used by VSeeFace's published Vita example. Normalization removes authored bone
rest rotations. The adapter therefore sends motion relative to Forge's world
rest frames, expressed as receiver-local rotations. A source T-pose produces
identity rotations; it does not send the reference asset's original bone axes
to the receiver. [@vseeFacePreviewNormalizer; @vseeFacePreviewReceiver]

`forge_reference_vrm_original` remains available for a receiver using that exact
original reference rig. The VMC specification's recommendation for original
VRM1 transforms does not make this profile suitable for normalized VRM0 avatars.
[@vmcProtocolSpecification; @vrmAvatarFeatures]

Neither profile changes Forge geometry, acquisition timestamps, or measured
capture coordinates. Positions are converted from millimeters to Unity meters.
The pelvis position is sent once through Root; Hips local position is zero.
This preserves the measurement origin, which can be below or outside the
receiver's default camera. No automatic recentering is implemented.

Only finite, valid bone branches with valid ancestors are sent. A receiver can
retain the preceding transform of an omitted bone. Reloading the avatar after
changing profiles can clear a pose left by the old binding; missing measurements
are not synthesized.

Available fingers are included by default. Missing finger measurements or a
body-only model do not suppress valid body bones. The advanced VMC settings include
a finger checkbox that starts enabled; disabling it sends `include_fingers=false`.
The Outputs popup has
separate VMC and LSL sections, each with its own settings and Start/Stop controls.
Stop an active output before starting it with changed settings.

The public preview receiver can apply incoming bone positions directly. Its
behavior does not establish the installed VSeeFace application's position
settings or arbitrary-avatar proportion compatibility. Rendered acceptance,
root placement, and partial-body behavior still require live review. Existing
outputs keep their chosen profile; create a new output after loading the updated
backend to use the new default. Runtime protocol discovery supplies the profile
enum/default; the generic OpenAPI configuration object has no embedded profile
schema to regenerate.
