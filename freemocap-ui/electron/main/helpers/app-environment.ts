
// Export the ENV_CONFIG object using the process.env values
export const APP_ENVIRONMENT = {
    IS_DEV: process.env.NODE_ENV === 'development',
    SHOULD_LAUNCH_PYTHON:  false,

};
