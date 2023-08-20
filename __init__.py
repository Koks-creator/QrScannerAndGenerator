from datetime import timedelta
from flask import Flask
import cv2

app = Flask(__name__)
app.secret_key = "guhijih454551"
QR_SIZE_RANGE = (1, 50)
QR_BORDER_RANGE = (1, 10)
QR_DETECTOR = cv2.QRCodeDetector()
temporary_qr_data = {}

from kuEry.QrWebApp import routes
