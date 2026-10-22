[app]
title = Calculadora
package.name = calc
package.domain = org.calc
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
source.exclude_dirs = .git,.github,bin,dist,tools,__pycache__,.buildozer
version = 1.0
requirements = python3,kivy,requests,urllib3,certifi,chardet,idna,psutil
orientation = portrait
fullscreen = 1
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,READ_MEDIA_IMAGES
android.api = 34
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True
android.allow_backup = True
android.wakelock = False
p4a.branch = master

[buildozer]
log_level = 2
warn_on_root = 1
