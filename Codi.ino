
//Llibreries
#include "KIM.h"
#include <SoftwareSerial.h>
#include <Arduino.h>
#include <EEPROM.h>
#include <avr/sleep.h>
#include <Wire.h>
#include "RTClib.h"
#include "previpass.h"


/*-- CONFIGURACIÓ --*/ //{

  //------ Definim paràmetres del SPP de Kinéis ---------------------------------------------------------------------------------

    int secondsBeforeNextStatellite;
    int Decimal_CoverageDuration;
    String messageLogFile = "";
    float MinElev =30.0f; //Elevació mínima
    float MinDur =4.0f; //Duració mínima

  //------ CONFIGURACIÓ DE PAS DE SATÈL·LIT ----------------------------------------------------------------------------------
    struct AopSatelliteEntry_t aopTable[] = {
      { 0x1, 8, SAT_DNLK_OFF, SAT_UPLK_ON_WITH_A2, {2024, 7, 22, 5, 28, 4}, 7130.963, 98.3492, 175.276, -24.978, 99.9095, -3.02}, // CS
      { 0xB, 7, SAT_DNLK_ON_WITH_A3, SAT_UPLK_ON_WITH_A2, {2024, 7, 22, 6, 22, 1}, 7199.946, 98.7262, 227.123, -25.340, 101.3606, 0.00}, // MC
      { 0x5, 0, SAT_DNLK_OFF, SAT_UPLK_ON_WITH_A2, {2024, 7, 22, 5, 37, 29}, 7182.560, 98.5717, 205.785, -25.249, 100.9943, -2.72}, // NK
      { 0x8, 0, SAT_DNLK_OFF, SAT_UPLK_ON_WITH_A2, {2024, 7, 22, 6, 4, 47}, 7227.779, 98.8785, 249.238, -25.487, 101.9489, -2.10}, // NN
      { 0xC, 6, SAT_DNLK_OFF, SAT_UPLK_ON_WITH_A2, {2024, 7, 22, 6, 43, 58}, 7228.495, 99.0498, 218.937, -25.489, 101.9634, -2.56}, // NP
      { 0x2, 9, SAT_DNLK_OFF, SAT_UPLK_ON_WITH_A2, {2024, 7, 22, 6, 48, 9}, 7115.051, 98.3589, 258.284, -24.894, 99.5744, 0.00}, // O3
      { 0xD, 4, SAT_DNLK_ON_WITH_A3, SAT_UPLK_ON_WITH_A2, {2024, 7, 22, 6, 50, 36}, 7163.127, 98.5571, 345.743, -25.146, 100.5847, 0.00}  // SR
    };
    uint8_t nbSatsInAopTable = 7;  //Els satèl·lits A1, MA i MB s'han tret degut a un mal funcionament. Poden afegir-se però no surt a compte.


  /*-- cONFIGURACIÓ DEL CODI --*/

    #define maxmessages 30

    double gpsLat, gpsLong;

    char PWR[] = "750";  //Potència (100, 250, 500, 750, 1000) 
    char AFMT[] ="1";  //Format del missatge

    SoftwareSerial kserial(RX_KIM, TX_KIM);
    KIM kim(&kserial);

    RTC_DS3231 rtc;

    const int wakeUpPin = 2;
    int messageCount = 0;
    int antialarma = 0;

//}

void setup() {
  Serial.begin(9600);
  Serial.println();
  Serial.println("Example KIM1 Arduino shield");
  configureKIM(); //Configurem els paràmetres del kinéis
  Serial.println("Config. KIM done");
  delay(100);
  Wire.begin();
  rtc.begin(); //Inicialitzem el RTC
  rtc.disable32K();
  pinMode(wakeUpPin, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(wakeUpPin), RTCAlarm, CHANGE);
  rtc.clearAlarm(1);
  rtc.writeSqwPinMode(DS3231_OFF);
  gpsLat = 41.223; //Latitud
  gpsLong = 1.736; //Longitud

}

void loop() {
  int messageCount = 0; //Llegim l'últim valor del comptador EEPROM
  Serial.println("Counter: " + String(messageCount) + ", Antialarma: " + String(antialarma));

  secondsBeforeNextStatellite = NextSatellite(gpsLat, gpsLong, aopTable, nbSatsInAopTable); //Retorna el temps per al pròxim pas de satèl·lit en segons
  //secondsBeforeNextStatellite=300; //Forçar temps
  Serial.println(secondsBeforeNextStatellite);
  unsigned long duracionMilisegundos = (unsigned long)secondsBeforeNextStatellite*1000UL; //Convertim segons a milisegons
  unsigned long tiempoInicio = millis(); //Guardem el temps d'inici de la funció
  while (millis() - tiempoInicio < duracionMilisegundos) { //Enviem missatges durant el temps marcat per la funció del SPP
    SentMsg(messageCount);
  }
}

void configureKIM() { //Comprobem que el kinéis funciona correctament
  Serial.println("KIM Initial Setup ---->");
  while (!kim.check()) {
    Serial.println("Failed connection to KIM module. Retrying in 3s...");
    delay(1000);
  }
  kim.set_PWR(PWR, sizeof(PWR) - 1);  // AT+PWR=1  & AT+AFMT=1  &  AT+SAVE_CFG  --> Aquests comandaments es guarden a la RAM (Nou predeterminat). 
  delay(1000);
  kim.set_AFMT(AFMT, sizeof(AFMT) - 1); //Format de missatge: Format kinéis
  delay(1000); 
  if (kim.save_CFG() == OK_KIM) { //Guardem els paràmetres
    Serial.println("State 0 - Kim Configuration_OK");
  } else {
    Serial.println("State 0 - Kim Configuration_ERR");
  }
  delay(1000); 
}

void SentMsg(int &messageCount) {
  //while (antialarma < maxmessages) {
    /*
    float sum = 0; // Variable to store the sum of the measurements
    for (int i = 0; i < 100; i++) {
      sum += analogRead(A0) * (5.0 / 1023.0); // Sum each reading converted to voltage
      delay(10); // Wait 10 milliseconds between each reading
    }
    float averageVoltage = (sum / 100.0) * 1000; // Calculate the average by dividing the sum by the number of measurements
    Serial.print("Voltage=");
    Serial.print(averageVoltage); // Print the average voltage with 3 decimals
    Serial.println("mV");
    */
    int hexdataLength = snprintf(NULL, 0, "%010X", (unsigned int)atoi(PWR)) + 1; //Creem una string per a guardar el valor de la potència
    hexdataLength += snprintf(NULL, 0, "%04X", (unsigned int)messageCount); //Creem una string per a guardar el valor del comptador
    char *hexdata = new char[hexdataLength];
    snprintf(hexdata, hexdataLength, "%04X%010X", (unsigned int)messageCount, (unsigned int)atoi(PWR)); //Unim les dues string amb el format correcte d'enviament
    //snprintf(hexdata, hexdataLength, "%016X%08X000000", (unsigned int)messageCount, (unsigned int)averageVoltage); //Unim les dues string amb el format correcte d'enviament
    
    Serial.print("KIM -- Send data ... ");
    Serial.println(hexdata);
    if (kim.send_data(hexdata, hexdataLength - 1) == OK_KIM) { //Envia el missatge de la string concatenada
      Serial.println("Message sent");
    } else {
      Serial.println("Error");
    }
    delete[] hexdata;
    messageCount++; //Augmentem el comptador
    antialarma++;
    delay(29000); //Es recomana enviar un missatge cada 30 segons
    delay(int(atoi(PWR))*2); //Aquest temps d'espera descoordina els arduinos per a evitar que enviïn alhora
  //}
}

void GoToSleepRTC(int8_t sleepingHours, int8_t sleepingMinute, int8_t sleepingSecond) { //Dorm l'arduino fins el pròxim pas de satèl·lit
  set_sleep_mode(SLEEP_MODE_PWR_DOWN);
  antialarma=0; //Comptador que evita que passi massa temps sense dormir degut a sobreposició de passos de satèl·lit
  rtc.clearAlarm(1); //Reset de l'alarma
  if (!rtc.setAlarm1(rtc.now() + TimeSpan(0, sleepingHours, sleepingMinute, sleepingSecond), DS3231_A1_Hour)) {
    Serial.println("Error, alarm wasn't set!");
  } else {    
    rtc.setAlarm1(rtc.now() + TimeSpan(0, sleepingHours, sleepingMinute, sleepingSecond), DS3231_A1_Hour);
    
    //Alarma + mode
    DateTime alarm1 = rtc.getAlarm1();
    Ds3231Alarm1Mode alarm1mode = rtc.getAlarm1Mode();
    char alarm1Date[12] = "DD hh:mm:ss";
    alarm1.toString(alarm1Date);
    Serial.print("[Alarm1: ");
    Serial.print(alarm1Date);
    Serial.print(", Mode: ");
    switch (alarm1mode) {
      case DS3231_A1_PerSecond: Serial.print("PerSecond"); break;
      case DS3231_A1_Second: Serial.print("Second"); break;
      case DS3231_A1_Minute: Serial.print("Minute"); break;
      case DS3231_A1_Hour: Serial.print("Hour"); break;
      case DS3231_A1_Date: Serial.print("Date"); break;
      case DS3231_A1_Day: Serial.print("Day"); break;
    }
    Serial.println("]");
    delay(1000);
    sleep_enable();
    sleep_mode();
    sleep_disable();
  }
}

int NextSatellite(double &gpsLat, double &gpsLong, AopSatelliteEntry_t *aopTable, uint8_t nbSatsInAopTable) {

  DateTime now = rtc.now();

  uint16_t gpsYear = now.year();
  uint8_t gpsMonth = now.month();
  uint8_t gpsDay = now.day();
  uint8_t gpsHour = now.hour();
  uint8_t gpsMinute = now.minute();
  uint8_t gpsSecond = now.second();

  Serial.print(gpsYear);
  Serial.print("/");
  Serial.print(gpsMonth);
  Serial.print("/");
  Serial.print(gpsDay);
  Serial.print(" ");
  Serial.print(gpsHour);
  Serial.print(":");
  Serial.print(gpsMinute);
  Serial.print(":");
  Serial.println(gpsSecond);

  int nextDay = gpsDay;
  int nextMonth = gpsMonth;
  int nextYear = gpsYear;

  if (nextDay == 30 || nextDay == 31) {
    nextDay = 1;
    nextMonth += 1;
    if (nextMonth >= 12) {
      nextMonth = 1;
      nextYear += 1;
    }
  } else {
    nextDay += 1;
  }

  struct PredictionPassConfiguration_t prepasConfiguration = {
    gpsLat,                                                           //< Geodetic latitude of the beacon (deg.) [-90, 90]
    gpsLong,                                                          //< Geodetic longitude of the beacon (deg.E)[0, 360]
    { gpsYear, gpsMonth, gpsDay, gpsHour, gpsMinute, gpsSecond },     //< Beginning of prediction (Y/M/D, hh:mm:ss)
    { nextYear, nextMonth, nextDay, gpsHour, gpsMinute, gpsSecond },  //< End of prediction (Y/M/D, hh:mm:ss)
    MinElev,                                                             //< Minimum elevation of passes [0, 90](default 5 deg)
    90.0f,                                                            //< Maximum elevation of passes  [maxElevation >=
                                                                      //< minElevation] (default 90 deg)
    MinDur,                                                             //< Minimum duration (default 5 minutes)
    1000,                                                             //< Maximum number of passes per satellite (default
                                                                      //< 1000)
    5,                                                                //< Linear time margin (in minutes/6months) (default
                                                                      //< 5 minutes/6months)
    30                                                                //< Computation step (default 30s)
  };

  struct SatelliteNextPassPrediction_t nextPass;
  struct SatelliteNextPassPrediction_t earliestPass;

  for (uint8_t i = 0; i < nbSatsInAopTable; i++) {
    PREVIPASS_compute_next_pass(&prepasConfiguration, &aopTable[i], 1, &nextPass);
    if (i == 0 || nextPass.epoch < earliestPass.epoch) {  // Comparison with time now so it won't bring back a SPP already begun
      earliestPass = nextPass;
      delay(100);
    }
  }
  //messageLogFile = "For the SPP : Next satellite epoch : " + String(earliestPass.epoch) + " and epoch now : " + String(now.unixtime());
  //writeLogFile(messageLogFile);

  //! Sat name
  char satNameTwoChars[3];

  switch (earliestPass.satHexId) {
    case 0x2:
      strcpy(satNameTwoChars, "03");
      break;
    case 0x6:
      strcpy(satNameTwoChars, "A1");
      break;
    case 0xA:
      strcpy(satNameTwoChars, "MA");
      break;
    case 0x9:
      strcpy(satNameTwoChars, "MB");
      break;
    case 0xB:
      strcpy(satNameTwoChars, "MC");
      break;
    case 0x5:
      strcpy(satNameTwoChars, "NK");
      break;
    case 0x8:
      strcpy(satNameTwoChars, "NN");
      break;
    case 0xC:
      strcpy(satNameTwoChars, "NP");
      break;
    case 0xD:
      strcpy(satNameTwoChars, "SR");
      break;
    default:
      strcpy(satNameTwoChars, "XX");
  }

  struct CalendarDateTime_t viewable_timedata;

  PREVIPASS_UTIL_date_stu90_calendar(earliestPass.epoch - EPOCH_90_TO_70_OFFSET,
                                     &viewable_timedata);

  

  
  String response = "Data: " + String(viewable_timedata.gpsDay) + "/" + String(viewable_timedata.gpsMonth) + "/" + String(viewable_timedata.gpsYear) + ".  The next satellite will be " 
  + String(satNameTwoChars) +     " at " + String(viewable_timedata.gpsHour) + ":" + String(viewable_timedata.gpsMinute) + ":" + String(viewable_timedata.gpsSecond) + "UTC, with a duration of " 
  + String(int(earliestPass.duration) / 60) + " min and "  + String(int(earliestPass.duration) % 60) + " sec and a maximum elevation of " + String(int(earliestPass.elevationMax)) + "º.";
  Serial.println(response);
  

  DateTime now3 = rtc.now();

  DateTime compareTime = DateTime(viewable_timedata.gpsYear, viewable_timedata.gpsMonth, viewable_timedata.gpsDay, viewable_timedata.gpsHour, viewable_timedata.gpsMinute, viewable_timedata.gpsSecond);

  // Calculate difference between the 2 times in seconds
  int diff = compareTime.unixtime() - now3.unixtime();

  Serial.print("Time now: ");
  Serial.println(now3.timestamp(DateTime::TIMESTAMP_FULL));
  Serial.print("Time SPP: ");
  Serial.println(compareTime.timestamp(DateTime::TIMESTAMP_FULL));
  Serial.print("Difference in seconds: ");
  Serial.println(diff);

  messageLogFile = "Next Satelitte : Time before next satellite :" + String(diff) + " sec and coverage : " + String(Decimal_CoverageDuration) + String(" sec");
  Serial.println(messageLogFile);

  int final=diff+int(earliestPass.duration); //Ens dona el temps en el que acaba el pas de satèl·lit


  if (diff>0) { //Esperem per al pròxim pas de satèl·lit
    GoToSleepRTC((diff/3600),((diff%3600)/60),(diff%60)); //Convertim els segons a hora, minuts i segons i dormim l'arduino durant el temps marcat
    return int(earliestPass.duration); //Retorna la duració del pròxim pas de satèl·lit en segons
  } else if (diff<0 && final<30){ //Menys de 30 segons per al pròxim pas de satèl·lit
    GoToSleepRTC(0, 0, final); //Dorm i repeteix la funció SPP
    NextSatellite(gpsLat, gpsLong, aopTable, nbSatsInAopTable);
  } else if (diff<0 && final>30){ //Més de 30 segons per a que acabi l'actual pas de satèl·lit
    return final; //Retorna el temps per a que acabi l'actual pas de satèl·lit en segons
  }
}

void RTCAlarm() { //Provoca que l'arduino es desperti
  Serial.println("RTC Alarm triggered. Waking up...");
}
