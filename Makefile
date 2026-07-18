.PHONY: help devices ios ios-real ios-sim ios-clean disk android

help:
	@echo "Targets:"
	@echo "  make devices     - List connected devices/simulators"
	@echo "  make ios         - Run on the first connected real iOS device"
	@echo "  make ios-real    - Same as 'make ios'"
	@echo "  make ios-sim     - Run on a booted iOS simulator"
	@echo "  make ios-clean   - flutter clean + reinstall CocoaPods (fixes stale-build errors)"
	@echo "  make disk        - Show free disk space (iOS builds need a few GB free)"
	@echo "  make android     - Run on a connected Android device/emulator"

devices:
	flutter devices

# Picks the first device whose flutter-devices line has platform "ios" and
# is NOT a simulator (real hardware only).
IOS_DEVICE_ID := $(shell flutter devices 2>/dev/null | awk -F'•' '/ios/ && !/simulator/ {gsub(/ /,"",$$2); print $$2; exit}')

ios ios-real: disk
	@if [ -z "$(IOS_DEVICE_ID)" ]; then \
		echo "No real iOS device found. Plug in your iPhone, unlock it, and trust this Mac if prompted."; \
		echo "Run 'make devices' to check what flutter currently sees."; \
		exit 1; \
	fi
	@echo "Running on device: $(IOS_DEVICE_ID)"
	flutter run -d $(IOS_DEVICE_ID)

# Picks the first booted iOS simulator; boots a default one if none is running.
IOS_SIM_ID := $(shell xcrun simctl list devices | awk '/Booted/ && /iPhone|iPad/ {match($$0, /\(([0-9A-F-]+)\)/); print substr($$0, RSTART+1, RLENGTH-2); exit}')

ios-sim: disk
	@if [ -z "$(IOS_SIM_ID)" ]; then \
		echo "No booted simulator found; boot one first, e.g.:"; \
		echo "  xcrun simctl list devices available | grep iPhone"; \
		echo "  xcrun simctl boot <device-id> && open -a Simulator"; \
		exit 1; \
	fi
	@echo "Running on simulator: $(IOS_SIM_ID)"
	flutter run -d $(IOS_SIM_ID)

ios-clean:
	flutter clean
	rm -rf ios/Pods ios/Podfile.lock
	flutter pub get
	@echo "Clean done. Re-run 'make ios' or 'make ios-sim'."

disk:
	@df -h / | awk 'NR==1 || NR==2'
	@avail_kb=$$(df -k / | awk 'NR==2 {print $$4}'); \
	if [ "$$avail_kb" -lt 3000000 ]; then \
		echo "Warning: less than ~3GB free. iOS builds may fail with 'No space left on device'."; \
	fi

android:
	flutter devices
	flutter run -d $$(flutter devices 2>/dev/null | awk -F'•' '/android/ {gsub(/ /,"",$$2); print $$2; exit}')
