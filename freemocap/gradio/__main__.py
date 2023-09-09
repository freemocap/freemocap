import gradio as gr


# Define a function to process the video
def process_video(input_video):
    print(input_video)
    # mocap(input_video)
    return "Video processing completed!"


with gr.Blocks() as app:
    gr.Markdown("# FreeMoCap")
    video = gr.File(
        label="Pick a video file",
        # height=int(1024 / 2),
        # width=int(576 / 2)
    )
    submit = gr.Button(value="Submit")
    submit.click(process_video, inputs=video)
# Launch the app
app.launch()
