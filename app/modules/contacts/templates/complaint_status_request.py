def complaint_status_email_template(
    name: str,
    complaint_id: str,
    old_status: str,
    new_status: str,
    support_email: str
):
    LOGO_URL = "https://res.cloudinary.com/dm6vq2px2/image/upload/v1766340950/logo_hr4wk0.jpg"
    STATUS_LABELS = {
        "open": "Abierto",
        "in_review": "En revisión",
        "resolved": "Resuelto",
        "rejected": "Rechazado"
    }
    old_label = STATUS_LABELS.get(old_status, old_status)
    new_label = STATUS_LABELS.get(new_status, new_status)
    return f"""
    <html>
    <body style="background:#f4f4f5;font-family:Arial,Helvetica,sans-serif;padding:20px;">
        <div style="
            max-width:600px;
            margin:auto;
            background:#ffffff;
            padding:30px;
            border-radius:8px;
            box-shadow:0 4px 10px rgba(0,0,0,0.05);
        ">
            <div style="text-align:center;margin-bottom:20px;">
                <img src="{LOGO_URL}" alt="Logo tienda"
                     style="max-width:160px;height:auto;" />
            </div>
            <h2 style="color:#3c495d;margin-bottom:10px;">RUC: 10481821211</h2>
            <h2 style="color:#334155;margin-bottom:10px;">
                Actualización de tu reclamo
            </h2>
            <p style="color:#475569;">
                Hola <strong>{name}</strong>,
            </p>
            <p style="color:#475569;">
                Queremos informarte que el estado de tu reclamo ha sido actualizado:
            </p>
            <div style="
                margin:20px 0;
                padding:15px;
                background:#f1f5f9;
                border-radius:6px;
                color:#334155;
                line-height:1.5;
            ">
                <p><strong>Reclamo:</strong> #{complaint_id}</p>
                <p><strong>Estado anterior:</strong> {old_label}</p>
                <p><strong>Estado actual:</strong> {new_label}</p>
            </div>
            <p style="color:#475569;">
                Si tienes alguna duda adicional, puedes responder a este correo o escribirnos a
                <a href="mailto:{support_email}">{support_email}</a>.
            </p>
            <p style="font-size:12px;color:#64748b;margin-top:25px;">
                Este es un mensaje automático. Por favor, no compartas información sensible por correo.
            </p>
        </div>
    </body>
    </html>
    """