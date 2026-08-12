# Aplicación de gestión de citas médicas

Aplicación Streamlit para reservar citas médicas (por web y por teléfono) de
seis profesionales, con agenda configurable y calendario mensual coloreado
según la ocupación del día.

## Características

La aplicación tiene dos zonas de acceso (selector en la barra lateral):

- **Público** (pacientes): pantalla con dos columnas — a la izquierda el
  **calendario mensual compacto** con código de color, y a la derecha la
  **agenda del día** (profesional y huecos libres), visible sin necesidad de
  desplazarse. Los días ya pasados aparecen en **marrón** y no son clicables
  (no se pueden solicitar citas para fechas pasadas). Al pulsar un día la
  agenda muestra los **huecos libres** de cada profesional. No muestra datos de
  otros pacientes. Al elegir **"Teléfono"** como tipo de cita se muestran de
  forma destacada los teléfonos de la clínica para llamar. Incluye la sección
  **"Mi cita"**: el paciente puede
  consultar y **anular su propia cita** introduciendo el código de la cita y su
  email o teléfono.
- **Zona clínica** (personal): protegida por código de acceso. Permite ver la
  **agenda de cada profesional por separado** (selector de médico en "Citas del
  día"), **anular citas** de cualquier día, **registrar citas manuales**
  (teléfono) y configurar médicos, intervalos y horarios, y **dar de alta o de
  baja a profesionales** (la baja elimina también sus horarios y citas, con
  confirmación previa). Dispone además de **"Imprimir agenda"** — vista
  compacta con una línea por paciente (hora, apellidos y nombre, sociedad y
  teléfono, lista para imprimir con Ctrl+P) — y de un **listado descargable en
  CSV** compatible con Excel (columnas separadas, abre directamente).

### Código de acceso de la clínica

La clave por defecto es `clinic2026`. Se puede cambiar con la variable de
entorno `CLINIC_PIN`:

```bash
CLINIC_PIN=otraclave streamlit run app.py
```

### Calendario con código de color

- :green_circle: Verde — menos de un tercio de la agenda citada.
- :orange_circle: Ámbar — se ha citado en torno a un tercio.
- :red_circle: Rojo — citada la mitad o más (hasta el total).
- Al pulsar sobre un día se muestran las agendas de ese día y se puede
  **seleccionar el profesional** que se desea consultar.

### Más características

- **Seis profesionales** de distintas especialidades, cada uno con su agenda.
- **Agenda configurable** por profesional: días de cita, intervalo entre
  citas y horarios de mañana y de tarde (zona clínica → *Configuración*).
- **Formulario de cita** con nombre y apellidos en tres campos separados,
  teléfono (validado: 9 dígitos), email y compañía de seguro (o paciente
  privado), y tipo de cita **web** o **teléfono**.
- **Correo automático**: al confirmar una cita se envía al solicitante una
  copia por email; al anularla (desde la clínica o por el propio paciente)
  se envía el aviso de cancelación.
- **SMS de aviso (Afilnet)**: opcional y configurable. Si se indican las
  credenciales de Afilnet, al confirmar una cita se envía un SMS de
  confirmación y al anularla un SMS de aviso al teléfono del paciente.

## Correo electrónico (opcional)

El envío de correos usa SMTP y está activado solo si se configuran las
variables de entorno:

```bash
SMTP_HOST=smtp.gmail.com SMTP_PORT=587 SMTP_USER=tucuenta SMTP_PASS=tuclave \
SMTP_FROM=clinica@example.com streamlit run app.py
```

Sin estas variables la app funciona igual pero no envía correos.

## SMS (opcional, Afilnet)

El envío de SMS usa la API de Afilnet y está activado solo si se configuran
las credenciales (variables de entorno o fichero `sms_credentials.json`):

```bash
AFILNET_USER=tucuenta AFILNET_PASS=tuclave AFILNET_FROM=CLINICA \
streamlit run app.py
```

Fichero `sms_credentials.json`:

```json
{"afilnet_user": "tucuenta", "afilnet_password": "tuclave", "from": "CLINICA"}
```

El teléfono del paciente se envía en formato internacional (+34). Sin
credenciales la app funciona igual pero no envía SMS.

## Puesta en marcha

```bash
pip install -r requirements.txt
streamlit run app.py
```

Los datos se guardan en `data/citas.db` (SQLite). En el primer arranque se
crean los 6 médicos con horario de lunes a viernes (mañana 9–14 y tarde
16–20). Para usar otra base de datos:

```bash
CITAS_DB_PATH=otra.db streamlit run app.py
```

## Pruebas

```bash
python -m pytest tests -q
```

Las pruebas cubren la generación de huecos, las validaciones de paciente, los
tres niveles de ocupación, la persistencia, el flujo completo de reserva a
través de la interfaz (AppTest), el acceso por PIN a la zona clínica, el
registro y anulación de citas desde el panel clínico y la privacidad de la
zona pública (no filtra datos de otros pacientes). Usan bases de datos
temporales y no tocan `data/citas.db`.

## Estructura

- `core.py` — lógica pura (huecos, ocupación, validaciones, calendario mensual).
- `services.py` — capa de servicios que conecta el núcleo con la persistencia.
- `storage.py` — repositorio SQLite (`medicos`, `horarios`, `citas`).
- `ui.py` — generador del HTML del calendario mensual.
- `mailing.py` — envío de correos de confirmación y anulación (SMTP opcional).
- `sms.py` — envío de SMS de confirmación y anulación (Afilnet opcional).
- `app.py` — aplicación Streamlit (zona pública + zona clínica).
- `tests/` — pruebas automatizadas.