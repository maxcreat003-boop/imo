FROM budtmo/docker-android:emulator_9.0

USER root

# Install system dependencies required for automation
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-full \
    adb \
    procps \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Setup Virtual Environment
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy project files
COPY . .

# Grant execute permissions
RUN chmod +x /app/final_start.sh

# Create the supervisor config for our automation
RUN echo "[program:automation]\ncommand=/bin/bash /app/final_start.sh\nautostart=true\nautorestart=false\nuser=root\nstdout_logfile=/var/log/automation.log\nstderr_logfile=/var/log/automation.err.log" > /etc/supervisor/conf.d/automation.conf

# Inject the include directive into the base image's supervisor config
# This natively starts our script alongside all emulator services WITHOUT breaking the base entrypoint.
RUN echo "\n[include]\nfiles = /etc/supervisor/conf.d/*.conf" >> /home/androidusr/docker-android/mixins/configs/process/supervisord-base.conf

# Bypass strict KVM requirement for hosts without hardware virtualization
RUN sed -i 's/raise RuntimeError("\/dev\/kvm cannot be found!")/self.logger.warning("KVM missing. Falling back to slow software emulation.")/g' /home/androidusr/docker-android/cli/src/device/emulator.py

# Prepare APK path
RUN mkdir -p /data/local/tmp/ && \
    if [ -f "apk/imo_lite.apk" ]; then cp apk/imo_lite.apk /data/local/tmp/imo_lite.apk; fi

# Install Python requirements
RUN /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# VNC Access
EXPOSE 6080

# Keep the base image's native ENTRYPOINT and CMD intact.
