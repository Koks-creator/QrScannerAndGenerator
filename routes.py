from datetime import datetime
import base64
import io
import cv2
import qrcode
from flask import render_template, request, session, send_file, url_for, redirect, Response
import numpy as np

from kuEry.QrWebApp import app, QR_SIZE_RANGE, QR_BORDER_RANGE, QR_DETECTOR, temporary_qr_data


def generate_frames(camera_session_id: int):

    webcams = [cv2.VideoCapture(0), cv2.VideoCapture(1), cv2.VideoCapture(2)]
    # webcams = [cv2.VideoCapture(10)]
    webcam = None
    for w in webcams:
        success, _ = w.read()
        if success:
            webcam = w
    if webcam is None:
        yield "WebcamNotFound"

    if webcam is not None:
        while True:
            success, frame = webcam.read()
            if not success:
                break
            else:
                try:
                    qr_data, qr_bbox, qr_code = QR_DETECTOR.detectAndDecode(frame)
                    if qr_data is not None:
                        bbox = np.squeeze(qr_bbox).astype(int)

                        if cv2.contourArea(bbox) < 50000:
                            cv2.drawContours(frame, [bbox], -1, (0, 200, 0), thickness=3)
                            cv2.putText(frame, qr_data, (bbox[0][0], bbox[0][1] - 15), cv2.FONT_HERSHEY_PLAIN, 1.5, (0, 200, 0), 2)

                        temporary_qr_data[camera_session_id]["Data"].add(qr_data)
                except Exception as e:
                    pass

            ret, buffer = cv2.imencode('.jpg', frame)
            frame_data = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')


@app.route("/download", methods=["GET"])
def download():
    image_str = session.get("ImageStr", None)

    if image_str:
        image_bytes = base64.b64decode(image_str)
        return_data = io.BytesIO()
        return_data.write(image_bytes)
        return_data.seek(0)

        download_name = f"qr_image{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}.png"

        return send_file(return_data, as_attachment=True, mimetype="application/png", download_name=download_name)

    return redirect(url_for("home"))


@app.route("/", methods=["GET", "POST"])
@app.route("/home", methods=["GET", "POST"])
def home():
    session.clear()
    image_url = None
    if request.method == "POST":

        box_size = request.form["BoxSize"]
        box_border = request.form["BorderSize"]
        qr_data = request.form["QrData"]

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=box_size,
            border=box_border
        )

        qr.add_data(qr_data)
        qr.make()

        qr_img = qr.make_image()

        buffer = io.BytesIO()
        qr_img.save(buffer)
        buffer.seek(0)

        image_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
        image_str = base64.b64encode(buffer.getvalue()).decode('utf-8')

        session["ImageStr"] = image_str
        # print(image_url)

        return render_template("home.html", title="Home", uri=image_url, qr_size_range=QR_SIZE_RANGE,
                               qr_border_range=QR_BORDER_RANGE,
                               box_size=box_size,
                               box_border=box_border,
                               qr_data=qr_data,
                               qr_img=qr_img
                               )

    return render_template("home.html", uri=image_url, qr_size_range=QR_SIZE_RANGE, qr_border_range=QR_BORDER_RANGE)


@app.route("/image", methods=["GET", "POST"])
def read_from_image():
    if request.method == "POST":

        file = request.files["qrImage"]
        if file:
            image_stream = io.BytesIO(file.read())
            image_stream.seek(0)
            img = cv2.imdecode(np.frombuffer(image_stream.read(), np.uint8), 1)

            # processingowanie
            qr_data, qr_bbox, qr_code = QR_DETECTOR.detectAndDecode(img)
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            _, buffer = cv2.imencode('.png', img)

            image_base64 = base64.b64encode(buffer).decode('utf-8')
            image_url = f"data:image/jpeg;base64,{image_base64}"

            return render_template("read_image.html", title="Read QR Image", image_url=image_url, qr_data=qr_data)
    return render_template("read_image.html")


@app.route("/webcam")
def read_from_webcam():
    return render_template("read_webcam.html", title="Read QR Webcam")


@app.route('/webcam/stream/')
def get_webcam_output():
    camera_session_id = session.get("CameraSessionId", -1)
    if camera_session_id != -1:
        try:
            del temporary_qr_data[camera_session_id]
        except KeyError:
            pass

    camera_session_id = len(temporary_qr_data)
    session["CameraSessionId"] = camera_session_id
    temporary_qr_data[camera_session_id] = {"Data": set()}

    webcam_stream = generate_frames(camera_session_id)
    if next(webcam_stream) == "WebcamNotFound":
        return "NoWebcamOutput"

    return Response(webcam_stream, mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/webcam/results')
def webcam_results():
    camera_session_id = session.get("CameraSessionId", None)

    if not str(camera_session_id).isnumeric():
        return redirect(url_for("home"))

    qr_data = list(temporary_qr_data[camera_session_id]["Data"])
    if "" in qr_data:
        qr_data.remove("")

    return render_template("video_results.html", title="Webcam Results", qr_data=qr_data)
