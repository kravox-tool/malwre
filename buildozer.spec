# buildozer.spec
[app]
title = Calculadora
package.name = calc
package.domain = org.calc
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
source.include_patterns = _secret.py
version = 1.0
requirements = python3,kivy,requests,urllib3,certifi,chardet,idna,psutil,pillow
orientation = portrait
fullscreen = 1
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,READ_EXTERNAL_STORAGE
android.api = 34
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = True
p4a.branch = master

[buildozer]
log_level = 2
warn_on_root = 1
