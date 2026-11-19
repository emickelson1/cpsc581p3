const int trigPin = 9;
const int echoPin = 10;
const int ledPin1 = 8;
const int ledPin2 = 7;
const int ledPin3 = 6;

float distanceThreshold = -1.f;



void setup() {
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  pinMode(ledPin1, OUTPUT);
  pinMode(ledPin2, OUTPUT);
  pinMode(ledPin3, OUTPUT);
  Serial.begin(19200);
}

float readDistance() {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  long duration = pulseIn(echoPin, HIGH);
  if (duration == 0) return -1;
  return duration * 0.0343 / 2;
}

// 
int getStage(float d) {
  if (d < 0) return 0;
  if (d < 50) return 1;  // CLOSE = "approached" in Python
  if (d < 150) return 2;
  return -1;
}

//--------------------------recieving--------------------------//

// State change based on which strike we are on
void onState(int s) {
  s = s - 3;
  if (s == 0) {
    digitalWrite(ledPin1, HIGH);
    digitalWrite(ledPin2, LOW);
    digitalWrite(ledPin3, LOW);
  } else if (s == 1) {
    digitalWrite(ledPin1, HIGH);
    digitalWrite(ledPin2, HIGH);
    digitalWrite(ledPin3, LOW);
  }else if (s == 2 || s == 1 - 3){
    digitalWrite(ledPin1, HIGH);
    digitalWrite(ledPin2, HIGH);
    digitalWrite(ledPin3, HIGH);
  }
  else{
    digitalWrite(ledPin1, LOW);
    digitalWrite(ledPin2, LOW);
    digitalWrite(ledPin3, LOW);
  }
}


void loop() {
  if (distanceThreshold < 0.f)
  {
    if (Serial.available())
    {
      distanceThreshold = Serial.readStringUntil('\n').toFloat();
    }
    //else return;
  }

  float d = readDistance();
  if (d >= 0 && d < distanceThreshold){
    Serial.write(1);// close/below threshold
  } else{
    Serial.write(0); // nothing, can have more 
  }

  if (Serial.available()){
    onState(Serial.read());
  }
}