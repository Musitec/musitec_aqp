def request_email_template(
    name: str,
    email: str,
    subject: str,
    message: str
):
    LOGO_URL = "https://res.cloudinary.com/dm6vq2px2/image/upload/v1766340950/logo_hr4wk0.jpg"
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
                Nueva solicitud recibida
            </h2>
            <p style="color:#475569;">
                Has recibido una nueva solicitud desde el formulario web:
            </p>
            <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0;" />
            <p><strong>Nombre:</strong> {name}</p>
            <p><strong>Email:</strong> {email}</p>
            <p><strong>Asunto:</strong> {subject}</p>
            <div style="
                margin-top:20px;
                padding:15px;
                background:#f1f5f9;
                border-radius:6px;
                color:#334155;
                line-height:1.5;
            ">
                {message}
            </div>
            <p style="font-size:12px;color:#64748b;margin-top:25px;">
                Este mensaje fue enviado desde el formulario web de la tienda.
            </p>
        </div>
    </body>
    </html>
    """