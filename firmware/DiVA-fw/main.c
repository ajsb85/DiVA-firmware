#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <crc.h>
#include <stdint.h>
#include <stdbool.h>

#include <console.h>
#include "include/hyperram.h"
#include "include/settings.h"
#include "include/time.h"
#include "include/terminal.h"
#include "include/boson.h"

#include <scaler.h>

#include <generated/csr.h>
#include <generated/mem.h>
#include <generated/git.h>

#include <irq.h>

#include <ppu.h>


#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#include "tusb.h"

/* prototypes */
void isr(void);

#define USB_INTERRUPT 4

extern volatile uint32_t system_ticks;
void isr(void){
	__attribute__((unused)) unsigned int irqs;

	irqs = irq_pending() & irq_getmask();

	
  if (irqs & (1 << USB_INTERRUPT)) {
    tud_int_handler(0);
  }
  
  if (irqs & (1 << TIMER0_INTERRUPT)) {
    system_ticks++;
    timer0_ev_pending_write(1);
  }
}

void led_blinking_task(void);
void cdc_task(void);

int main(int i, char **c)
{	
//	irq_setie(1);

//	gui_init();


//	ppu_start();

  //board_init();
  irq_setmask(0);
  irq_setie(1);
  
  timer_init();
  tusb_init();

	while(1){
    tud_task(); // tinyusb device task
    cdc_task();
    led_blinking_task();

    int b_val = button_raw_read();
    if(b_val & BUTTON_A_HOLD){
      reboot_ctrl_write(0xac);
    }
	}


	
	return 0;
}





/* Blink pattern
 * - 250 ms  : device not mounted
 * - 1000 ms : device mounted
 * - 2500 ms : device is suspended
 */
enum  {
  BLINK_NOT_MOUNTED = 250,
  BLINK_MOUNTED = 1000,
  BLINK_SUSPENDED = 2500,
};

static uint32_t blink_interval_ms = BLINK_NOT_MOUNTED;

//--------------------------------------------------------------------+
// USB CDC
//--------------------------------------------------------------------+
void cdc_task(void)
{
  // connected() check for DTR bit
  // Most but not all terminal client set this when making connection
  // if ( tud_cdc_connected() )
  {
    // connected and there are data available
    if ( tud_cdc_available() )
    {
      // read datas
      char buf[64];
      uint32_t count = tud_cdc_read(buf, sizeof(buf));
      (void) count;

      // Echo back
      // Note: Skip echo by commenting out write() and write_flush()
      // for throughput test e.g
      //    $ dd if=/dev/zero of=/dev/ttyACM0 count=10000
      tud_cdc_write(buf, count);
      tud_cdc_write_flush();
    }
  }
}

// Invoked when cdc when line state changed e.g connected/disconnected
void tud_cdc_line_state_cb(uint8_t itf, bool dtr, bool rts)
{
  (void) itf;
  (void) rts;

  // TODO set some indicator
  if ( dtr )
  {
    // Terminal connected
  }else
  {
    // Terminal disconnected
  }
}

// Invoked when CDC interface received data from host
void tud_cdc_rx_cb(uint8_t itf)
{
  (void) itf;
}

//--------------------------------------------------------------------+
// Device callbacks
//--------------------------------------------------------------------+

// Invoked when device is mounted
void tud_mount_cb(void)
{
  blink_interval_ms = BLINK_MOUNTED;
}

// Invoked when device is unmounted
void tud_umount_cb(void)
{
  blink_interval_ms = BLINK_NOT_MOUNTED;
}

// Invoked when usb bus is suspended
// remote_wakeup_en : if host allow us  to perform remote wakeup
// Within 7ms, device must draw an average of current less than 2.5 mA from bus
void tud_suspend_cb(bool remote_wakeup_en)
{
  (void) remote_wakeup_en;
  blink_interval_ms = BLINK_SUSPENDED;
}

// Invoked when usb bus is resumed
void tud_resume_cb(void)
{
  blink_interval_ms = BLINK_MOUNTED;
}



//--------------------------------------------------------------------+
// BLINKING TASK
//--------------------------------------------------------------------+
void led_blinking_task(void)
{
  static uint32_t start_ms = 0;
  static bool led_state = false;

  // Blink every interval ms
  if ( board_millis() - start_ms < blink_interval_ms) return; // not enough time
  start_ms += blink_interval_ms;

  
  board_led_write(led_state);
    static count = 0;
  //printf("Hello\n");
  if( tud_cdc_connected()){
    char str[256];
    sprintf(str, "Hello! %u\r\n", count++);

    tud_cdc_write_str(str);
    tud_cdc_write_flush();
  }
  led_state = 1 - led_state; // toggle
}



void board_led_write(bool state)
{
	leds_out_write(state ? 1 : 0);
}
