const int trigPin = 9;
const int echoPin = 10;
const int ledPin1 = 8;
const int ledPin2 = 7;
const int ledPin3 = 6;


// Minimum distance (in metres) away from the ultrasonic sensor without
// causing the device to enter the APPROACHED state.
float distanceThreshold = 20.f;



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
  return duration * 0.0343 * 0.5;
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
  switch (s)
  {
    case 0:
      digitalWrite(ledPin1, LOW);
      digitalWrite(ledPin2, LOW);
      digitalWrite(ledPin3, LOW);
      break;
    case 1:
    case 2:
    case 5:
      digitalWrite(ledPin1, HIGH);
      digitalWrite(ledPin2, HIGH);
      digitalWrite(ledPin3, HIGH);
      break;
    case 3:
      digitalWrite(ledPin1, HIGH);
      digitalWrite(ledPin2, LOW);
      digitalWrite(ledPin3, LOW);
      break;
    case 4:
      digitalWrite(ledPin1, HIGH);
      digitalWrite(ledPin2, HIGH);
      digitalWrite(ledPin3, LOW);
      break;
  }
}


void loop() {
  float d = readDistance();
  if (d > 0 && d < distanceThreshold){
    Serial.write(1);// close/below threshold
  } else{
    Serial.write(0); // nothing, can have more 
  }

  if (Serial.available()){
    onState(Serial.read());
  }
}