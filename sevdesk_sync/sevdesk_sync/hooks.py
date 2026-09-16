from . import __version__ as app_version  # noqa: F401

app_name = "sevdesk_sync"
app_title = "SevDesk Sync"
app_publisher = "Dr. Dot House"
app_description = (
    "Sync gross prices from ERPNext's standard selling price list to sevDesk"
    " as net prices."
)
app_email = "drdothouse@gmail.com"
app_license = "MIT"

# Scheduled Tasks
# ---------------

scheduler_events = {
    "daily": [
        "sevdesk_sync.tasks.scheduled_sync",
    ]
}
