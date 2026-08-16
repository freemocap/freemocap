# FreeMoCap localization maintenance

English (`en-english.json`) is the source locale. Simplified Chinese
(`zh-CN-zhongwen.json`) intentionally has strict leaf-key parity with English;
all other locales may continue to fall back to English when a key is missing.

Run the following before committing UI changes:

```sh
npm run i18n:check
npm exec tsc -- --noEmit
```

The localization check verifies English/Chinese key parity, interpolation
placeholders, literal `t()` references, native-menu keys, and common visible
English literals in TSX. Technical names, units, raw logs, stack traces, file
paths, model identifiers, and third-party error details should remain unchanged.
Translate the surrounding explanation and suggested action instead.

The renderer, Redux, and Electron menu share the persisted locale key
`freemocap:locale`. Do not introduce a second locale storage key. Legacy
`skellycam:*` keys are read only for one-time migration.

## Simplified Chinese terminology

| English | Simplified Chinese |
| --- | --- |
| motion capture / mocap | 动作捕捉 |
| frame rate | 帧率 |
| exposure | 曝光 |
| keypoint / landmark | 关键点 |
| skeleton tracking | 骨架追踪 |
| calibration | 标定 |
| triangulation | 三角测量 |
| reprojection error | 重投影误差 |
| realtime pipeline | 实时管线 |
| post-processing | 后处理 |
| center of mass (COM) | 质心 |
| viewport | 视口 |

Keep FreeMoCap, Blender, CUDA, FPS, WebSocket, ChArUco, MediaPipe,
RTMPose, YOLOX, TOML, TRC, OpenSim, and file extensions in their established
forms. The Chinese locale remains marked `translationSource: "ai-generated"`
until a complete human review has been recorded; only then should it change to
`human-validated`.

## Updating from upstream

1. Sync upstream `main`, then merge it into the maintained Chinese branch.
2. Run `npm run i18n:check` to identify new English keys and visible literals.
3. Add the English source text and professional Simplified Chinese together,
   preserving every `{{placeholder}}` exactly.
4. Review the affected screen at 100%, 125%, and 150% Windows display scaling.
5. Run type checks and the Windows package smoke tests before distributing a
   rebuilt installer.
