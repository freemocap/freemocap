from PySide6.QtCore import qVersion
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import QApplication, QStyleFactory, QWidget, QHBoxLayout


def class_name(o):
    return o.metaObject().className()


def help_url(page):
    """Build a Qt help URL from the page name"""
    major_version = qVersion().split('.')[0]
    return f"https://doc.qt.io/qt-{major_version}/{page}.html"


def launch_help(widget):
    """Launch a widget's help page"""
    url = help_url(class_name(widget).lower())
    QDesktopServices.openUrl(url)


def launch_module_help():
    QDesktopServices.openUrl(help_url("qtwidgets-index"))


def init_widget(w, name):
    """Init a widget for the gallery, give it a tooltip showing the
       class name"""
    w.setObjectName(name)
    w.setToolTip(class_name(w))


def style_names():
    """Return a list of styles, default platform style first"""
    default_style_name = QApplication.style().objectName().lower()
    result = []
    for style in QStyleFactory.keys():
        if style.lower() == default_style_name:
            result.insert(0, style)
        else:
            result.append(style)
    return result


def embed_into_hbox_layout(w, margin=5):
    """Embed a widget into a layout to give it a frame"""
    result = QWidget()
    layout = QHBoxLayout(result)
    layout.setContentsMargins(margin, margin, margin, margin)
    layout.addWidget(w)
    return result


def format_geometry(rect):
    """Format a geometry as a X11 geometry specification"""
    w = rect.width()
    h = rect.height()
    x = rect.x()
    y = rect.y()
    return f"{w}x{h}{x:+d}{y:+d}"


def screen_info(widget):
    """Format information on the screens"""
    policy = QGuiApplication.highDpiScaleFactorRoundingPolicy()
    policy_string = str(policy).split('.')[-1]
    result = f"<p>High DPI scale factor rounding policy: {policy_string}</p><ol>"
    for screen in QGuiApplication.screens():
        current = screen == widget.screen()
        result += "<li>"
        if current:
            result += "<i>"
        name = screen.name()
        geometry = format_geometry(screen.geometry())
        dpi = int(screen.logicalDotsPerInchX())
        dpr = screen.devicePixelRatio()
        result += f'"{name}" {geometry} {dpi}DPI, DPR={dpr}'
        if current:
            result += "</i>"
        result += "</li>"
    result += "</ol>"
    return result
