#include <Wire.h>
#include <SPI.h>
#include <Adafruit_BMP280.h>
#include <DHT.h>
#include <DHT_U.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <MQUnifiedsensor.h>

// --- Konfigurasi WiFi ---
const char* ssid = "ssid_wifi";
const char* password = "password_wifi";

// --- Konfigurasi MQTT ---
const char* mqttServer = "127.0.0.1";
const int mqttPort = 1883;

// --- Objek WiFi dan MQTT ---
WiFiClient espClient;
PubSubClient client(espClient);

// --- Konfigurasi GUVA-S12SD (Sensor UV) ---
const int uvPin = 6;
float uvVoltage = 0.0;
float uvIntensity = 0.0;

// --- Konfigurasi BMP280 (Suhu, Tekanan, Ketinggian) ---
Adafruit_BMP280 bmp;

// --- Konfigurasi DHT11 (Suhu dan Kelembaban) ---
#define DHTPIN 17
#define DHTTYPE DHT11
DHT dht(DHTPIN, DHTTYPE);

// --- Konfigurasi MQ-135 (Kualitas Udara) ---
#define placa "ESP32"
#define Voltage_Resolution 3.3
#define MQpin 15
#define type "MQ-135" // MQ135
#define ADC_Bit_Resolution 12 // For ESP32
#define RatioMQ135CleanAir 3.6 // RS / R0 = 3.6 ppm
MQUnifiedsensor MQ135(placa, Voltage_Resolution, ADC_Bit_Resolution, MQpin, type);

char jenisgas[6][10] = {"CO", "Alcohol", "CO2", "Tolueno", "NH4", "Aceton"};
float gasA[6] = {605.18, 77.255, 110.47, 44.947, 102.2, 34.668};
float gasB[6] = {-3.937, -3.18, -2.862, -3.445, -2.473, -3.369};
int itemcheck = 0;

// --- Fungsi untuk menghubungkan ke WiFi ---
void setupWiFi() {
  Serial.print("Menghubungkan ke WiFi: ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi terhubung!");

  Serial.print("Alamat IP: ");
  Serial.println(WiFi.localIP());
}

// --- Fungsi untuk menghubungkan ke MQTT ---
void setupMQTT() {
  client.setServer(mqttServer, mqttPort);
  while (!client.connected()) {
    Serial.print("Menghubungkan ke MQTT...");
    if (client.connect("ESP32Client")) {
      Serial.println("Terhubung ke MQTT broker!");
    } else {
      Serial.print("Gagal terhubung, rc=");
      Serial.print(client.state());
      Serial.println(" Coba lagi dalam 5 detik...");
      delay(5000);
    }
  }
}

void setup() {
  Serial.begin(115200);

  // Inisialisasi WiFi dan MQTT
  setupWiFi();
  setupMQTT();

  // Inisialisasi sensor GUVA-S12SD (UV)
  pinMode(uvPin, INPUT);

  // Inisialisasi BMP280
  Serial.println(F("Inisialisasi BMP280..."));
  if (!bmp.begin(0x76)) {
    Serial.println(F("Sensor BMP280 tidak ditemukan!"));
    while (1) delay(10);
  }
  bmp.setSampling(Adafruit_BMP280::MODE_NORMAL,
                  Adafruit_BMP280::SAMPLING_X2,
                  Adafruit_BMP280::SAMPLING_X16,
                  Adafruit_BMP280::FILTER_X16,
                  Adafruit_BMP280::STANDBY_MS_500);

  // Inisialisasi DHT11
  Serial.println("Inisialisasi sensor DHT11...");
  dht.begin();

  // Inisialisasi sensor MQ-135
  Serial.println("Inisialisasi sensor MQ-135...");
  MQ135.setRegressionMethod(1); 
  MQ135.setA(gasA[itemcheck]); MQ135.setB(gasB[itemcheck]);

  // Calibration of MQ135
  Serial.print("Calibrating MQ135 please wait.");
  float calcR0 = 0;
  for (int i = 1; i <= 10; i++) {
    MQ135.update();
    calcR0 += MQ135.calibrate(RatioMQ135CleanAir);
    Serial.print(".");
  }
  MQ135.setR0(calcR0 / 10);
  Serial.println(" done!");
  if (isinf(calcR0)) {
    Serial.println("Warning: Connection issue found, R0 is infinite (Open circuit detected) please check your wiring and supply");
    while (1);
  }
  if (calcR0 == 0) {
    Serial.println("Warning: Connection issue found, R0 is zero (Analog pin with short circuit to ground) please check your wiring and supply");
    while (1);
  }
  MQ135.serialDebug(false);
}

void loop() {
  // Pastikan terhubung ke MQTT
  if (!client.connected()) {
    setupMQTT();
  }
  client.loop();

  // --- Membaca sensor GUVA-S12SD (UV) ---
  int uvAnalogValue = analogRead(uvPin);
  uvVoltage = (uvAnalogValue / 4095.0 * 3.3) * 1000;

  // --- Membaca sensor BMP280 ---
  float bmpTemperature = bmp.readTemperature();
  float bmpPressure = bmp.readPressure() / 100.0F;
  float bmpAltitude = bmp.readAltitude(1013.25);

  // --- Membaca sensor DHT11 ---
  float humidity = dht.readHumidity();
  float dht_temperature = dht.readTemperature();

  // --- Membaca sensor MQ-135 ---
  MQ135.update();
  float aqi = MQ135.readSensor();

  // --- Pilih suhu otomatis ---
  float autoTemperature;
  if (!isnan(bmpTemperature)) {
    autoTemperature = bmpTemperature;
  } else {
    autoTemperature = dht_temperature;
  }

  // --- Publikasikan data melalui MQTT ---
  client.publish("sensor/uv/voltage", String(uvVoltage).c_str());

  client.publish("sensor/bmp/temperature", String(bmpTemperature).c_str());
  client.publish("sensor/bmp/pressure", String(bmpPressure).c_str());
  client.publish("sensor/bmp/altitude", String(bmpAltitude).c_str());

  client.publish("sensor/dht/temperature", String(dht_temperature).c_str());
  client.publish("sensor/dht/humidity", String(humidity).c_str());

  client.publish("sensor/mq135/ppm", String(aqi).c_str());

  client.publish("sensor/auto/temperature", String(autoTemperature).c_str());

  // Tampilkan data ke Serial Monitor
  Serial.print("Temperature (BMP280): ");
  Serial.print(bmpTemperature);
  Serial.println(" *C");

  Serial.print("Pressure: ");
  Serial.print(bmpPressure);
  Serial.println(" hPa");

  Serial.print("Altitude: ");
  Serial.print(bmpAltitude);
  Serial.println(" m");

  Serial.print("DHT11 - Suhu: ");
  Serial.print(dht_temperature);
  Serial.print(" °C, Kelembaban: ");
  Serial.print(humidity);
  Serial.println(" %");

  Serial.print("MQ-135 ");
  Serial.print(jenisgas[itemcheck]);
  Serial.print(": ");
  Serial.print(aqi);
  Serial.println(" PPM");

  Serial.print("Auto Temperature: ");
  Serial.print(autoTemperature);
  Serial.println(" °C");

  delay(2000);
}