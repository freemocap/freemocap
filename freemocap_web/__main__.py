import gradio as gr
from freemocap_web.core import mocap


def greet(video_input):
    moc = mocap(video_input)
    blender = moc.to_blender()
    return blender


if __name__ == '__main__':
    with gr.Blocks() as demo:
        gr.Markdown('# FreeMoCap')
        with gr.Row():
            video = gr.Video(
                label="Name",
                width=288,
                height=512)
            with gr.Column():
                greet_btn = gr.Button("Mocap")
                out_put = gr.File()
                greet_btn.click(fn=greet, inputs=video, outputs=out_put, api_name="greet")

    demo.launch()
