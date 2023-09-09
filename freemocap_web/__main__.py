import gradio as gr
from freemocap_web.core import mocap


def mocap_hook(video_input):
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
                mocap_button = gr.Button("Mocap")
                output = gr.File()
                mocap_button.click(fn=mocap_hook, inputs=video, outputs=output)

    demo.launch()
