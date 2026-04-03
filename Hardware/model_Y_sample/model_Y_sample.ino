/*  ___   ___  ___  _   _  ___   ___   ____ ___  ____  
 * / _ \ /___)/ _ \| | | |/ _ \ / _ \ / ___) _ \|    \ 
 *| |_| |___ | |_| | |_| | |_| | |_| ( (__| |_| | | | |
 * \___/(___/ \___/ \__  |\___/ \___(_)____)___/|_|_|_|
 *                  (____/ 
 * OSOYOO Model Y H-bridge Board Sample Code
 * Tutorial URL https://osoyoo.com/2022/02/25/osoyoo-model-y-4-channel-motor-driver/
 * CopyRight www.osoyoo.com
 */
#define SPEED               100 //speed is PWM value between 0 to 255
#define TURN_SPEED          100 //speed is PWM value between 0 to 255
#define Speed_BK1_Socket    9   //BK1 Motor Socket Speed controlled by Model-Y Channel-B ENA PWM value
#define Chnl_B_IN1          22  //BK1 Motor Rotate Direction control pin 1 is Channel-B IN1 
#define Chnl_B_IN2          24  //BK1 Motor Rotate Direction control pin 2 is Channel-B IN2                               
#define Chnl_B_IN3          26  //BK3 Motor Rotate Direction control pin 1 is Channel-B IN3  
#define Chnl_B_IN4          28  //BK3 Motor Rotate Direction control pin 2 is Channel-B IN4 
#define Speed_BK3_Socket    10  //BK3 Motor Socket Speed controlled by Model-Y Channel-B ENB PWM value

#define Speed_AK1_Socket    11  //AK1 Motor Socket Speed controlled by Model-Y Channel-A ENA PWM value
#define Chnl_A_IN1          5   //AK1 Motor Rotate Direction control pin 1 is Channel-A IN1
#define Chnl_A_IN2          6   //AK1 Motor Rotate Direction control pin 2 is Channel-A IN2
#define Chnl_A_IN3          7   //AK3 Motor Rotate Direction control pin 1 is Channel-A IN3
#define Chnl_A_IN4          8   //AK3 Motor Rotate Direction control pin 2 is Channel-A IN4 (K3)
#define Speed_AK3_Socket    12  //AK3 Motor Socket Speed controlled by Model-Y Channel-A  ENB PWM value

void BK1_fwd(int speed)  //front-right wheel forward turn
{
  digitalWrite(Chnl_B_IN1,HIGH);
  digitalWrite(Chnl_B_IN2,LOW); 
  analogWrite(Speed_BK1_Socket,speed);
}
void BK1_bck(int speed) // front-right wheel backward turn
{
  digitalWrite(Chnl_B_IN1,LOW);
  digitalWrite(Chnl_B_IN2,HIGH); 
  analogWrite(Speed_BK1_Socket,speed);
}
void BK3_fwd(int speed) // front-left wheel forward turn
{
  digitalWrite(Chnl_B_IN3,HIGH);
  digitalWrite(Chnl_B_IN4,LOW);
  analogWrite(Speed_BK3_Socket,speed);
}
void BK3_bck(int speed) // front-left wheel backward turn
{
  digitalWrite(Chnl_B_IN3,LOW);
  digitalWrite(Chnl_B_IN4,HIGH);
  analogWrite(Speed_BK3_Socket,speed);
}

void AK1_fwd(int speed)  //rear-right wheel forward turn
{
  digitalWrite(Chnl_A_IN1, HIGH);
  digitalWrite(Chnl_A_IN2,LOW); 
  analogWrite(Speed_AK1_Socket,speed);
}
void AK1_bck(int speed)  //rear-right wheel backward turn
{
  digitalWrite(Chnl_A_IN1, LOW);
  digitalWrite(Chnl_A_IN2,HIGH); 
  analogWrite(Speed_AK1_Socket,speed);
}
void AK3_fwd(int speed)  //rear-left wheel forward turn
{
  digitalWrite(Chnl_A_IN3,HIGH);
  digitalWrite(Chnl_A_IN4,LOW);
  analogWrite(Speed_AK3_Socket,speed);
}
void AK3_bck(int speed)    //rear-left wheel backward turn
{
  digitalWrite(Chnl_A_IN3,LOW);
  digitalWrite(Chnl_A_IN4,HIGH);
  analogWrite(Speed_AK3_Socket,speed);
}
 
void stop_motor()    //Stop
{
  analogWrite(Speed_AK3_Socket,0);
  analogWrite(Speed_AK1_Socket,0);
  analogWrite(Speed_BK3_Socket,0);
  analogWrite(Speed_BK1_Socket,0);
}


//Pins initialize
void init_GPIO()
{
  pinMode(Chnl_A_IN1, OUTPUT); 
  pinMode(Chnl_A_IN2, OUTPUT); 
  pinMode(Chnl_A_IN3, OUTPUT);
  pinMode(Chnl_A_IN4, OUTPUT); 
  pinMode(Speed_AK1_Socket, OUTPUT);
  pinMode(Speed_AK3_Socket, OUTPUT);  
  pinMode(Chnl_B_IN1, OUTPUT); 
  pinMode(Chnl_B_IN2, OUTPUT); 
  pinMode(Chnl_B_IN3, OUTPUT);
  pinMode(Chnl_B_IN4, OUTPUT); 
  pinMode(Speed_BK1_Socket, OUTPUT);
  pinMode(Speed_BK3_Socket, OUTPUT);  
  stop_motor();
}

void setup()
{
  init_GPIO();
  AK1_fwd(SPEED);
  delay(800);
  stop_motor();
  delay(100);
  
  AK1_bck(SPEED);
  delay(800);
  stop_motor();
  delay(100);
 
  AK3_fwd(SPEED);
  delay(800);
  stop_motor();
  delay(100);
  
  AK3_bck(SPEED);
  delay(800);
  stop_motor();
  delay(100);

  BK1_fwd(SPEED);
  delay(800);
  stop_motor();
  delay(100);
  
  BK1_bck(SPEED);
  delay(800);
  stop_motor();
  delay(100); 
  
  BK3_fwd(SPEED);
  delay(800);
  stop_motor();
  delay(100);
  
  BK3_bck(SPEED);
  delay(800);
  stop_motor();

}

void loop(){
}
