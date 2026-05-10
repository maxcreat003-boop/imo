FROM budtmo/docker-android:emulator_9.0

# 1. Force Software Emulation (TCG) & Resource Optimization
ENV EMULATOR_ADDITIONAL_ARGS="-accel tcg -no-window -no-snapshot -no-audio"
ENV DEVICE_OPTS="-gpu off"
ENV SCREEN_WIDTH=320
ENV SCREEN_HEIGHT=480
ENV SCREEN_DPI=160

# 2. System Packages
USER root
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    adb \
    procps \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 3. Environment Setup
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN /opt/venv/bin/pip install --no-cache-dir \
    python-telegram-bot>=21.0 \
    psutil==5.9.5 \
    python-dotenv==1.0.0

# 4. Cleanup Unnecessary Services to save RAM on Railway
RUN rm -f /etc/supervisor/conf.d/appium.conf \
    /etc/supervisor/conf.d/vnc_web.conf \
    /etc/supervisor/conf.d/log_web_shared.conf

# 5. Application Files
WORKDIR /app
COPY . /app/
RUN chmod +x /app/final_start.sh

# 6. Supervisor Injection (Parallel Execution v5.5)
RUN printf "[program:automation]\ncommand=/app/final_start.sh\nautostart=true\nautorestart=false\nuser=root\nstdout_logfile=/home/androidusr/logs/automation.stdout.log\nstderr_logfile=/home/androidusr/logs/automation.stderr.log\n" > /etc/supervisor/conf.d/automation.conf

# Bypass strict KVM check (Allow TCG Software fallback)
RUN sed -i 's/raise RuntimeError("\/dev\/kvm cannot be found!")/self.logger.warning("KVM missing. Falling back to Software TCG.")/g' /home/androidusr/docker-android/cli/src/device/emulator.py

# Ensure supervisor includes our config
RUN echo "\n[include]\nfiles = /etc/supervisor/conf.d/*.conf" >> /home/androidusr/docker-android/mixins/configs/process/supervisord-base.conf

EXPOSE 6080
# Base entrypoint handles supervisor launch
