def pin_email_template(name: str, pin: str):
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
                Verificación de cuenta
            </h2>
            <p style="color:#475569;">
                Hola <strong>{name}</strong>,  
                estamos a un paso de completar tu registro.
            </p>
            <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0;" />
            <p style="color:#475569;">
                Tu código de verificación es:
            </p>
            <div style="
                margin:25px 0;
                text-align:center;
                font-size:32px;
                letter-spacing:6px;
                font-weight:bold;
                color:#2563eb;
            ">
                {pin}
            </div>
            <p style="color:#475569;">
                Este código es válido por <strong>10 minutos</strong>.
                Si no solicitaste este registro, puedes ignorar este mensaje.
            </p>

            <p style="font-size:12px;color:#64748b;margin-top:25px;">
                Este mensaje fue enviado automáticamente por Musitec.
            </p>
        </div>
    </body>
    </html>
    """