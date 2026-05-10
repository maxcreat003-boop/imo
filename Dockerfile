FROM budtmo/docker-android:emulator_9.0

# [v7.0 ADAPTIVE CONFIG]
# Default to Software Mode for maximum compatibility
ENV EMULATOR_ADDITIONAL_ARGS="-accel tcg -memory 512 -no-window -no-snapshot -no-audio -no-boot-anim"
ENV DEVICE_OPTS="-gpu off"
ENV SCREEN_WIDTH=160
ENV SCREEN_HEIGHT=240
ENV SCREEN_DPI=120

USER root
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-venv adb procps wget curl \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN /opt/venv/bin/pip install --no-cache-dir \
    python-telegram-bot>=21.0 psutil==5.9.5 python-dotenv==1.0.0

# Strip bloatware services to save RAM
RUN rm -f /etc/supervisor/conf.d/appium.conf \
    /etc/supervisor/conf.d/vnc_web.conf \
    /etc/supervisor/conf.d/novnc.conf \
    /etc/supervisor/conf.d/fluxbox.conf \
    /etc/supervisor/conf.d/vnc_server.conf \
    /etc/supervisor/conf.d/log_web_shared.conf \
    /etc/supervisor/conf.d/android_port_forward.conf \
    /etc/supervisor/conf.d/d_screen.conf \
    /etc/supervisor/conf.d/d_wm.conf

WORKDIR /app
COPY . /app/
RUN chmod +x /app/final_start.sh

RUN printf "[program:automation]\ncommand=/app/final_start.sh\nautostart=true\nautorestart=false\nuser=root\nstdout_logfile=/home/androidusr/logs/automation.stdout.log\nstderr_logfile=/home/androidusr/logs/automation.stderr.log\n" > /etc/supervisor/conf.d/automation.conf

# Bypass KVM check in Python wrapper
RUN sed -i 's/raise RuntimeError("\/dev\/kvm cannot be found!")/self.logger.warning("KVM missing. Adaptive v7.0 TCG fallback.")/g' /home/androidusr/docker-android/cli/src/device/emulator.py

RUN echo "\n[include]\nfiles = /etc/supervisor/conf.d/*.conf" >> /home/androidusr/docker-android/mixins/configs/process/supervisord-base.conf

EXPOSE 6080
