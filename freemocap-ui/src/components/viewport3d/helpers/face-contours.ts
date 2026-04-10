/**
 * MediaPipe face mesh contour connections.
 * Point names follow `face.{group}_{mediapipe_index}`.
 */

interface FaceContourGroup {
    prefix: string;
    connections: [number, number][];
}

const FACE_CONTOUR_GROUPS: FaceContourGroup[] = [
    {
        prefix: "face.lips",
        connections: [
            [61,146],[146,91],[91,181],[181,84],[84,17],[17,314],[314,405],[405,321],[321,375],[375,291],
            [61,185],[185,40],[40,39],[39,37],[37,0],[0,267],[267,269],[269,270],[270,409],[409,291],
            [78,95],[95,88],[88,178],[178,87],[87,14],[14,317],[317,402],[402,318],[318,324],[324,308],
            [78,191],[191,80],[80,81],[81,82],[82,13],[13,312],[312,311],[311,310],[310,415],[415,308],
        ],
    },
    {
        prefix: "face.left_eye",
        connections: [
            [263,249],[249,390],[390,373],[373,374],[374,380],[380,381],[381,382],[382,362],
            [263,466],[466,388],[388,387],[387,386],[386,385],[385,384],[384,398],[398,362],
        ],
    },
    {
        prefix: "face.right_eye",
        connections: [
            [33,7],[7,163],[163,144],[144,145],[145,153],[153,154],[154,155],[155,133],
            [33,246],[246,161],[161,160],[160,159],[159,158],[158,157],[157,173],[173,133],
        ],
    },
    {
        prefix: "face.left_eyebrow",
        connections: [[276,283],[283,282],[282,295],[295,285],[300,293],[293,334],[334,296],[296,336]],
    },
    {
        prefix: "face.right_eyebrow",
        connections: [[46,53],[53,52],[52,65],[65,55],[70,63],[63,105],[105,66],[66,107]],
    },
    {
        prefix: "face.face_oval",
        connections: [
            [10,338],[338,297],[297,332],[332,284],[284,251],[251,389],[389,356],[356,454],
            [454,323],[323,361],[361,288],[288,397],[397,365],[365,379],[379,378],[378,400],
            [400,377],[377,152],[152,148],[148,176],[176,149],[149,150],[150,136],[136,172],
            [172,58],[58,132],[132,93],[93,234],[234,127],[127,162],[162,21],[21,54],[54,103],
            [103,67],[67,109],[109,10],
        ],
    },
    {
        prefix: "face.left_iris",
        connections: [[474,475],[475,476],[476,477],[477,474]],
    },
    {
        prefix: "face.right_iris",
        connections: [[469,470],[470,471],[471,472],[472,469]],
    },
];

export interface FaceSegment {
    from: string;
    to: string;
}

/** All face contour segments as pairs of point names. */
export const FACE_SEGMENTS: FaceSegment[] = [];

for (const group of FACE_CONTOUR_GROUPS) {
    for (const [a, b] of group.connections) {
        FACE_SEGMENTS.push({
            from: `${group.prefix}_${a}`,
            to: `${group.prefix}_${b}`,
        });
    }
}
