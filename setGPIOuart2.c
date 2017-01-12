#define _DEFAULT_SOURCE
#define _BSD_SOURCE


/*
 * base on pio.c from https://github.com/linux-sunxi/sunxi-tools/blob/master/pio.c
 * (C) Copyright 2011 Henrik Nordstrom <henrik@henriknordstrom.net>
 *
 *  modified by Daniel Perron (C) Copyright 2016
 *
 * This program will overwrite register settings to allow the utilisation of uart2
 * without recompiling the kernel for C.H.I.P. device
 *
 * works on os kernel 4.3 and 4.4
 * 
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License as
 * published by the Free Software Foundation; either version 2 of
 * the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston,
 * MA 02111-1307 USA
 */

#include <errno.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>
#include <stdlib.h>
#include <errno.h>
#include <sys/mman.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>

//#include "endian_compat.h"

#define PIO_REG_SIZE 0x228 /*0x300*/
#define PIO_PORT_SIZE 0x24

struct pio_status {
    int mul_sel;
    int pull;
    int drv_level;
    int data;
};

#define PIO_REG_CFG(B, N, I)    ((B) + (N)*0x24 + ((I)<<2) + 0x00)
#define PIO_REG_DLEVEL(B, N, I)    ((B) + (N)*0x24 + ((I)<<2) + 0x14)
#define PIO_REG_PULL(B, N, I)    ((B) + (N)*0x24 + ((I)<<2) + 0x1C)
#define PIO_REG_DATA(B, N)    ((B) + (N)*0x24 + 0x10)
#define PIO_NR_PORTS        9 /* A-I */

#define LE32TOH(X)        le32toh(*((uint32_t*)(X)))

void pio_print(char port_name, uint32_t port_num,struct pio_status *pio)
{
   printf("GPIO %c%d (",port_name,port_num);
   printf("mul_sel=%d, ",pio->mul_sel);
   printf("pull=%d, ",pio->pull);
   printf("drv_level=%d, ",pio->drv_level);
   printf("data=%d)\n",pio->data);
}

static int pio_get(const char *buf, char port_name, uint32_t port_num, struct pio_status *pio)
{
    uint32_t port = port_name - 'A';
    uint32_t val;
    uint32_t port_num_func, port_num_pull;
    uint32_t offset_func, offset_pull;

    port_num_func = port_num >> 3;
    offset_func = ((port_num & 0x07) << 2);

    port_num_pull = port_num >> 4;
    offset_pull = ((port_num & 0x0f) << 1);

    /* func */
    val = LE32TOH(PIO_REG_CFG(buf, port, port_num_func));
    pio->mul_sel = (val>>offset_func) & 0x07;

    /* pull */
    val = LE32TOH(PIO_REG_PULL(buf, port, port_num_pull));
    pio->pull = (val>>offset_pull) & 0x03;

    /* dlevel */
    val = LE32TOH(PIO_REG_DLEVEL(buf, port, port_num_pull));
    pio->drv_level = (val>>offset_pull) & 0x03;

    /* i/o data */
    if (pio->mul_sel > 1)
        pio->data = -1;
    else {
        val = LE32TOH(PIO_REG_DATA(buf, port));
        pio->data = (val >> port_num) & 0x01;
    }
    return 1;
}

static int pio_set(char *buf, char port_name, uint32_t port_num, struct pio_status *pio)
{
    uint32_t port = port_name - 'A';
    uint32_t *addr, val;
    uint32_t port_num_func, port_num_pull;
    uint32_t offset_func, offset_pull;

    port_num_func = port_num >> 3;
    offset_func = ((port_num & 0x07) << 2);

    port_num_pull = port_num >> 4;
    offset_pull = ((port_num & 0x0f) << 1);

    /* func */
    if (pio->mul_sel >= 0) {
        addr = (uint32_t*)PIO_REG_CFG(buf, port, port_num_func);
        val = le32toh(*addr);
        val &= ~(0x07 << offset_func);
        val |=  (pio->mul_sel & 0x07) << offset_func;
        *addr = htole32(val);
    }

    /* pull */
    if (pio->pull >= 0) {
        addr = (uint32_t*)PIO_REG_PULL(buf, port, port_num_pull);
        val = le32toh(*addr);
        val &= ~(0x03 << offset_pull);
        val |=  (pio->pull & 0x03) << offset_pull;
        *addr = htole32(val);
    }

    /* dlevel */
    if (pio->drv_level >= 0) {
        addr = (uint32_t*)PIO_REG_DLEVEL(buf, port, port_num_pull);
        val = le32toh(*addr);
        val &= ~(0x03 << offset_pull);
        val |=  (pio->drv_level & 0x03) << offset_pull;
        *addr = htole32(val);
    }

    /* data */
    if (pio->data >= 0) {
        addr = (uint32_t*)PIO_REG_DATA(buf, port);
        val = le32toh(*addr);
        if (pio->data)
            val |= (0x01 << port_num);
        else
            val &= ~(0x01 << port_num);
        *addr = htole32(val);
    }

    return 1;
}

int main()
{
    char *buff = malloc(PIO_REG_SIZE);
    int pagesize = sysconf(_SC_PAGESIZE);
    int addr = 0x01c20800 & ~(pagesize - 1);
    int offset = 0x01c20800 & (pagesize - 1);

    int fd = open("/dev/mem",O_RDWR);
    if (fd == -1) {
        perror("open /dev/mem");
        exit(1);
    }
    buff = mmap(NULL, (0x800 + pagesize - 1) & ~(pagesize - 1), PROT_WRITE | PROT_READ, MAP_SHARED, fd, addr);
    if (!buff) {
        perror("mmap PIO");
        exit(1);
    }
    close(fd);
    buff += offset;

    struct pio_status pio;
 
    pio.mul_sel=3;
    pio.pull=1;
    pio.drv_level=0;
    pio.data=-1;
    pio_set(buff, 'D', 2, &pio);
    pio_get(buff, 'D', 2, &pio);
    pio_print('D',2,&pio);


    pio.mul_sel=3;
    pio.pull=0;
    pio.drv_level=0;
    pio.data=-1;

    pio_set(buff, 'D', 3, &pio);
    pio_get(buff, 'D', 3, &pio);
    pio_print('D',3,&pio);

    return 0;
}
