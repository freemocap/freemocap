import {Canvas} from "@react-three/fiber";
import {ThreeJsScene} from "@/components/viewport3d/ThreeJsScene";
import {Box} from "@mui/material";


export function ThreeJsCanvas() {

    return (
       <Box sx={{width: '100%',
           height: '100%',
       }}>
            <Canvas
                shadows
                camera={{position: [5, 5, 5], fov: 75}}
            >
                <ThreeJsScene/>
            </Canvas>
         </Box>
    );
}



