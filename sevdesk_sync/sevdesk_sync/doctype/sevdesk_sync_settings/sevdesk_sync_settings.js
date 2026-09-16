frappe.ui.form.on("SevDesk Sync Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Verbindung testen"), () => {
			frappe.call({
				method: "sevdesk_sync.tasks.test_connection",
				freeze: true,
				freeze_message: __("Verbindung wird geprüft..."),
			}).then((r) => {
				frappe.msgprint({
					title: __("Verbindungstest"),
					message: r.message,
					indicator: "green",
				});
			});
		});

		frm.add_custom_button(__("Trockenlauf starten"), () => {
			frappe.call({
				method: "sevdesk_sync.tasks.run_dry_run",
				freeze: true,
				freeze_message: __("Trockenlauf läuft..."),
			}).then((r) => {
				frappe.msgprint({
					title: __("Trockenlauf abgeschlossen"),
					message: r.message,
					indicator: "blue",
				});
			});
		});
	},
});
