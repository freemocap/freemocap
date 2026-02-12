"""
Skeleton topology definitions for mediapipe body, hands, and face.

Key concepts:
    - Bone: directed parent→child edge with FABRIK length constraint.
      These define the tree structure for the FABRIK solver.
    - Connection: edge for visualization (superset of bones, includes
      non-constrained edges like torso cross-braces).
    - root_joints: joints held fixed during FABRIK solving.
    - The FABRIK tree is derived from bones + root_joints.
      Y-splits (one parent, multiple children) are natural.

Factory classmethods:
    SkeletonDefinition.mediapipe_body()
    SkeletonDefinition.mediapipe_left_hand()
    SkeletonDefinition.mediapipe_right_hand()
    SkeletonDefinition.mediapipe_face()
    SkeletonDefinition.mediapipe_full()
"""

from pydantic import BaseModel, ConfigDict, model_validator


# ============================================================
# Core Models
# ============================================================


class Bone(BaseModel):
    """Directed parent→child edge with a FABRIK length constraint."""

    model_config = ConfigDict(frozen=True)

    parent: str
    child: str

    @property
    def key(self) -> str:
        return f"{self.parent}->{self.child}"


class Connection(BaseModel):
    """Edge for visualization (may or may not be a FABRIK-constrained bone)."""

    model_config = ConfigDict(frozen=True)

    parent: str
    child: str


class SkeletonDefinition(BaseModel):
    """
    Skeleton topology as bones (FABRIK-constrained tree edges),
    connections (visualization edges), and root joints.

    The FABRIK tree is implicitly defined by ``bones`` + ``root_joints``:
    each root joint is a tree root, and bones define parent→child
    directed edges. Y-splits (one parent, multiple children) are
    represented naturally — a parent appearing in multiple bones.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    bones: tuple[Bone, ...]
    connections: tuple[Connection, ...]
    root_joints: frozenset[str]
    keypoint_names: frozenset[str]

    @model_validator(mode="after")
    def _validate_topology(self) -> "SkeletonDefinition":
        for bone in self.bones:
            if bone.parent not in self.keypoint_names:
                raise ValueError(f"Bone parent '{bone.parent}' not in keypoint_names")
            if bone.child not in self.keypoint_names:
                raise ValueError(f"Bone child '{bone.child}' not in keypoint_names")

        for conn in self.connections:
            if conn.parent not in self.keypoint_names:
                raise ValueError(f"Connection parent '{conn.parent}' not in keypoint_names")
            if conn.child not in self.keypoint_names:
                raise ValueError(f"Connection child '{conn.child}' not in keypoint_names")

        for root in self.root_joints:
            if root not in self.keypoint_names:
                raise ValueError(f"Root joint '{root}' not in keypoint_names")

        # No joint should have two parents (forest of trees, not DAG)
        child_parent: dict[str, str] = {}
        for bone in self.bones:
            if bone.child in child_parent:
                raise ValueError(
                    f"Joint '{bone.child}' has two parents: "
                    f"'{child_parent[bone.child]}' and '{bone.parent}' — "
                    f"skeleton bones must form a forest"
                )
            child_parent[bone.child] = bone.parent

        return self

    @classmethod
    def _collect_keypoint_names(
        cls,
        *,
        bones: tuple[Bone, ...],
        connections: tuple[Connection, ...],
    ) -> frozenset[str]:
        names: set[str] = set()
        for bone in bones:
            names.add(bone.parent)
            names.add(bone.child)
        for conn in connections:
            names.add(conn.parent)
            names.add(conn.child)
        return frozenset(names)

    @classmethod
    def merge(cls, *, name: str, skeletons: list["SkeletonDefinition"]) -> "SkeletonDefinition":
        """Merge multiple SkeletonDefinitions into one."""
        if not skeletons:
            raise ValueError("Need at least one skeleton to merge")

        all_bones: list[Bone] = []
        all_connections: list[Connection] = []
        all_roots: set[str] = set()
        all_keypoints: set[str] = set()
        seen_bones: set[tuple[str, str]] = set()
        seen_connections: set[tuple[str, str]] = set()

        for skel in skeletons:
            for bone in skel.bones:
                key = (bone.parent, bone.child)
                if key not in seen_bones:
                    seen_bones.add(key)
                    all_bones.append(bone)
            for conn in skel.connections:
                key = (conn.parent, conn.child)
                if key not in seen_connections:
                    seen_connections.add(key)
                    all_connections.append(conn)
            all_roots.update(skel.root_joints)
            all_keypoints.update(skel.keypoint_names)

        return cls(
            name=name,
            bones=tuple(all_bones),
            connections=tuple(all_connections),
            root_joints=frozenset(all_roots),
            keypoint_names=frozenset(all_keypoints),
        )

    # ============================================================
    # Mediapipe Body
    # ============================================================

    @classmethod
    def mediapipe_body(cls) -> "SkeletonDefinition":
        """
        Mediapipe pose (33 body landmarks).

        Root joints are the 4 torso corners (shoulders + hips).
        Limb bones form FABRIK trees branching from roots.
        Ankles Y-split into heel + foot_index.
        Torso cross-braces and head edges are connections only.
        """
        bones = tuple(
            Bone(parent=p, child=c) for p, c in (
                # Left arm
                ("left_shoulder", "left_elbow"),
                ("left_elbow", "left_wrist"),
                # Right arm
                ("right_shoulder", "right_elbow"),
                ("right_elbow", "right_wrist"),
                # Left leg + foot (Y-split at ankle)
                ("left_hip", "left_knee"),
                ("left_knee", "left_ankle"),
                ("left_ankle", "left_heel"),
                ("left_ankle", "left_foot_index"),
                # Right leg + foot (Y-split at ankle)
                ("right_hip", "right_knee"),
                ("right_knee", "right_ankle"),
                ("right_ankle", "right_heel"),
                ("right_ankle", "right_foot_index"),
            )
        )

        connections = tuple(
            Connection(parent=p, child=c) for p, c in (
                # Torso
                ("left_shoulder", "right_shoulder"),
                ("left_shoulder", "left_hip"),
                ("right_shoulder", "right_hip"),
                ("left_hip", "right_hip"),
                # Arms
                ("left_shoulder", "left_elbow"),
                ("left_elbow", "left_wrist"),
                ("left_wrist", "left_pinky"),
                ("left_wrist", "left_index"),
                ("left_wrist", "left_thumb"),
                ("left_pinky", "left_index"),
                ("right_shoulder", "right_elbow"),
                ("right_elbow", "right_wrist"),
                ("right_wrist", "right_pinky"),
                ("right_wrist", "right_index"),
                ("right_wrist", "right_thumb"),
                ("right_pinky", "right_index"),
                # Legs + feet
                ("left_hip", "left_knee"),
                ("left_knee", "left_ankle"),
                ("left_ankle", "left_heel"),
                ("left_ankle", "left_foot_index"),
                ("left_heel", "left_foot_index"),
                ("right_hip", "right_knee"),
                ("right_knee", "right_ankle"),
                ("right_ankle", "right_heel"),
                ("right_ankle", "right_foot_index"),
                ("right_heel", "right_foot_index"),
                # Head
                ("nose", "left_eye_inner"),
                ("left_eye_inner", "left_eye"),
                ("left_eye", "left_eye_outer"),
                ("left_eye_outer", "left_ear"),
                ("nose", "right_eye_inner"),
                ("right_eye_inner", "right_eye"),
                ("right_eye", "right_eye_outer"),
                ("right_eye_outer", "right_ear"),
                ("mouth_left", "mouth_right"),
            )
        )

        root_joints = frozenset({
            "left_shoulder", "right_shoulder",
            "left_hip", "right_hip",
        })

        return cls(
            name="mediapipe_body",
            bones=bones,
            connections=connections,
            root_joints=root_joints,
            keypoint_names=cls._collect_keypoint_names(bones=bones, connections=connections),
        )

    # ============================================================
    # Mediapipe Hands
    # ============================================================

    @classmethod
    def _mediapipe_hand(cls, *, side: str) -> "SkeletonDefinition":
        if side not in ("left", "right"):
            raise ValueError(f"side must be 'left' or 'right', got '{side}'")

        prefix = f"{side}_hand"

        def n(landmark: str) -> str:
            return f"{prefix}_{landmark}"

        bones = tuple(
            Bone(parent=n(p), child=n(c)) for p, c in (
                # 5 fingers Y-split from wrist
                ("wrist", "thumb_cmc"),
                ("thumb_cmc", "thumb_mcp"),
                ("thumb_mcp", "thumb_ip"),
                ("thumb_ip", "thumb_tip"),
                ("wrist", "index_finger_mcp"),
                ("index_finger_mcp", "index_finger_pip"),
                ("index_finger_pip", "index_finger_dip"),
                ("index_finger_dip", "index_finger_tip"),
                ("wrist", "middle_finger_mcp"),
                ("middle_finger_mcp", "middle_finger_pip"),
                ("middle_finger_pip", "middle_finger_dip"),
                ("middle_finger_dip", "middle_finger_tip"),
                ("wrist", "ring_finger_mcp"),
                ("ring_finger_mcp", "ring_finger_pip"),
                ("ring_finger_pip", "ring_finger_dip"),
                ("ring_finger_dip", "ring_finger_tip"),
                ("wrist", "pinky_mcp"),
                ("pinky_mcp", "pinky_pip"),
                ("pinky_pip", "pinky_dip"),
                ("pinky_dip", "pinky_tip"),
            )
        )

        connections = tuple(
            Connection(parent=n(p), child=n(c)) for p, c in (
                ("wrist", "thumb_cmc"),
                ("thumb_cmc", "thumb_mcp"),
                ("thumb_mcp", "thumb_ip"),
                ("thumb_ip", "thumb_tip"),
                ("wrist", "index_finger_mcp"),
                ("index_finger_mcp", "index_finger_pip"),
                ("index_finger_pip", "index_finger_dip"),
                ("index_finger_dip", "index_finger_tip"),
                ("wrist", "middle_finger_mcp"),
                ("middle_finger_mcp", "middle_finger_pip"),
                ("middle_finger_pip", "middle_finger_dip"),
                ("middle_finger_dip", "middle_finger_tip"),
                ("wrist", "ring_finger_mcp"),
                ("ring_finger_mcp", "ring_finger_pip"),
                ("ring_finger_pip", "ring_finger_dip"),
                ("ring_finger_dip", "ring_finger_tip"),
                ("wrist", "pinky_mcp"),
                ("pinky_mcp", "pinky_pip"),
                ("pinky_pip", "pinky_dip"),
                ("pinky_dip", "pinky_tip"),
                # Palm cross-braces
                ("index_finger_mcp", "middle_finger_mcp"),
                ("middle_finger_mcp", "ring_finger_mcp"),
                ("ring_finger_mcp", "pinky_mcp"),
            )
        )

        return cls(
            name=f"mediapipe_{prefix}",
            bones=bones,
            connections=connections,
            root_joints=frozenset({n("wrist")}),
            keypoint_names=cls._collect_keypoint_names(bones=bones, connections=connections),
        )

    @classmethod
    def mediapipe_left_hand(cls) -> "SkeletonDefinition":
        """Mediapipe left hand (21 landmarks, 5 fingers Y-split from wrist)."""
        return cls._mediapipe_hand(side="left")

    @classmethod
    def mediapipe_right_hand(cls) -> "SkeletonDefinition":
        """Mediapipe right hand (21 landmarks, 5 fingers Y-split from wrist)."""
        return cls._mediapipe_hand(side="right")

    # ============================================================
    # Mediapipe Face (Contours + Irises)
    # ============================================================

    @classmethod
    def mediapipe_face(cls) -> "SkeletonDefinition":
        """
        Mediapipe face mesh contours + irises.

        No FABRIK bones — the face is rigid, all landmarks are filter-only.
        Landmark names are ``face_{index}`` matching mediapipe mesh indices.
        """
        connections = tuple(
            Connection(parent=f"face_{a}", child=f"face_{b}")
            for a, b in _FACE_CONTOUR_CONNECTIONS
        )

        return cls(
            name="mediapipe_face",
            bones=(),
            connections=connections,
            root_joints=frozenset(),
            keypoint_names=cls._collect_keypoint_names(bones=(), connections=connections),
        )

    # ============================================================
    # Full Mediapipe
    # ============================================================

    @classmethod
    def mediapipe_full(cls) -> "SkeletonDefinition":
        """All mediapipe components merged into one skeleton."""
        return cls.merge(
            name="mediapipe_full",
            skeletons=[
                cls.mediapipe_body(),
                cls.mediapipe_left_hand(),
                cls.mediapipe_right_hand(),
                cls.mediapipe_face(),
            ],
        )


# ============================================================
# Face Mesh Contour + Iris Connection Data
# (from mediapipe.python.solutions.face_mesh_connections)
# ============================================================

_FACE_OVAL_CONNECTIONS: tuple[tuple[int, int], ...] = (
    (10, 338), (338, 297), (297, 332), (332, 284), (284, 251),
    (251, 389), (389, 356), (356, 454), (454, 323), (323, 361),
    (361, 288), (288, 397), (397, 365), (365, 379), (379, 378),
    (378, 400), (400, 377), (377, 152), (152, 148), (148, 176),
    (176, 149), (149, 150), (150, 136), (136, 172), (172, 58),
    (58, 132), (132, 93), (93, 234), (234, 127), (127, 162),
    (162, 21), (21, 54), (54, 103), (103, 67), (67, 109), (109, 10),
)

_LIPS_CONNECTIONS: tuple[tuple[int, int], ...] = (
    (61, 185), (185, 40), (40, 39), (39, 37), (37, 0),
    (0, 267), (267, 269), (269, 270), (270, 409), (409, 291),
    (61, 146), (146, 91), (91, 181), (181, 84), (84, 17),
    (17, 314), (314, 405), (405, 321), (321, 375), (375, 291),
    (78, 191), (191, 80), (80, 81), (81, 82), (82, 13),
    (13, 312), (312, 311), (311, 310), (310, 415), (415, 308),
    (78, 95), (95, 88), (88, 178), (178, 87), (87, 14),
    (14, 317), (317, 402), (402, 318), (318, 324), (324, 308),
)

_LEFT_EYE_CONNECTIONS: tuple[tuple[int, int], ...] = (
    (263, 249), (249, 390), (390, 373), (373, 374), (374, 380),
    (380, 381), (381, 382), (382, 362), (362, 466), (466, 388),
    (388, 387), (387, 386), (386, 385), (385, 384), (384, 398), (398, 263),
)

_RIGHT_EYE_CONNECTIONS: tuple[tuple[int, int], ...] = (
    (33, 7), (7, 163), (163, 144), (144, 145), (145, 153),
    (153, 154), (154, 155), (155, 133), (133, 246), (246, 161),
    (161, 160), (160, 159), (159, 158), (158, 157), (157, 173), (173, 33),
)

_LEFT_EYEBROW_CONNECTIONS: tuple[tuple[int, int], ...] = (
    (276, 283), (283, 282), (282, 295), (295, 285),
    (300, 293), (293, 334), (334, 296), (296, 336),
)

_RIGHT_EYEBROW_CONNECTIONS: tuple[tuple[int, int], ...] = (
    (46, 53), (53, 52), (52, 65), (65, 55),
    (70, 63), (63, 105), (105, 66), (66, 107),
)

_LEFT_IRIS_CONNECTIONS: tuple[tuple[int, int], ...] = (
    (468, 469), (469, 470), (470, 471), (471, 472),
)

_RIGHT_IRIS_CONNECTIONS: tuple[tuple[int, int], ...] = (
    (473, 474), (474, 475), (475, 476), (476, 477),
)

_FACE_CONTOUR_CONNECTIONS: tuple[tuple[int, int], ...] = (
    *_FACE_OVAL_CONNECTIONS,
    *_LIPS_CONNECTIONS,
    *_LEFT_EYE_CONNECTIONS,
    *_RIGHT_EYE_CONNECTIONS,
    *_LEFT_EYEBROW_CONNECTIONS,
    *_RIGHT_EYEBROW_CONNECTIONS,
    *_LEFT_IRIS_CONNECTIONS,
    *_RIGHT_IRIS_CONNECTIONS,
)
