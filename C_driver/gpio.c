/**
 * @brief gpio.c
 *
 */
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include "gpio.h"






unsigned char *map_base = NULL; // GPIO映射的虚拟内存基地址
int dev_fd;                     // 设备文件描述符

int file;

int gpio_init(void)
{
    //  “/dev/mem”设备是内核所有物理地址空间的全映像，这些地址包括：
    // 物理内存（RAM）空间
    // 物理存储（ROM）空间
    // CPU总线地址
    // CPU寄存器地址
    // 外设寄存器地址，GPIO、定时器、ADC
    dev_fd = open("/dev/mem", O_RDWR | O_SYNC); // open一个“/dev/mem”文件描述符，访问权限为读写（O_RDWR ）的阻塞或同步方式
    if (dev_fd < 0)
    {
        printf("\nopen(/dev/mem) failed.\n");
        return -1;
    }
    // 通过mmap把需访问的目标物理地址（这里是GPIO配置寄存器）与“/dev/mem”文件描述符建立映射。
    map_base = (unsigned char *)mmap(0, MAP_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, dev_fd, REG_BASE);
    return 0;
}

int gpio_enable(int gpio_num, int val)
{
    int offset, gpio_move;
    // 这里将GPIO端口转换位高32位和低32位按unsigned int进行按位操作。为什么不直接使用64位按位操作？？
    if (gpio_num > 31)
    {
        offset = 4;
        gpio_move = gpio_num - 32;
    }
    else
    {
        offset = 0;
        gpio_move = gpio_num;
    }
    if (val == 0)
    {
        // GPIO0_OEN（GPIO方向控制（GPIO输出使能），0为输出，1为输入）地址：0x1fe10500
        *(volatile unsigned int *)(map_base + GPIO_EN + offset) |= (1 << gpio_move); // GPIO使能in（地址写访问）
                                                                                     // printf("Enable GPIO%d in\n",gpio_num);
    }
    else
    {
        *(volatile unsigned int *)(map_base + GPIO_EN + offset) &= ~(1 << gpio_move); // GPIO使能out（地址写访问）
                                                                                      // printf("Enable GPIO%d out\n",gpio_num);
    }

    return 0;
}

int gpio_close(void)
{
    if (dev_fd < 0)
    {
        printf("\nopen(/dev/mem) failed.\n");
        return -1;
    }

    munmap(map_base, MAP_SIZE); // 解除映射关系
    if (dev_fd)
    {
        close(dev_fd);
    }
    map_base = NULL;
    return 0;
}

int gpio_write(int gpio_num, int val)
{
    int offset, gpio_move;

    if (gpio_num > 31)
    {
        offset = 4;
        gpio_move = gpio_num - 32;
    }
    else
    {
        offset = 0;
        gpio_move = gpio_num;
    }
    if (val == 1)
    {
        *(volatile unsigned int *)(map_base + GPIO_OUT + offset) |= (1 << gpio_move); // 输出高（地址写访问）
    }
    else
    {
        *(volatile unsigned int *)(map_base + GPIO_OUT + offset) &= ~(1 << gpio_move); // 输出低（地址写访问）
    }
    return 0;
}

int gpio_read(int gpio_num)
{
    int offset, gpio_move;

    if (gpio_num > 31)
    {
        offset = 4;
        gpio_move = gpio_num - 32;
    }
    else
    {
        offset = 0;
        gpio_move = gpio_num;
    }

    return (*(volatile unsigned int *)(map_base + GPIO_IN + offset) >> gpio_move) & 0x01; // 读取（地址读访问）
}

int gpio_model_set(int bit_num, int val)
{
    int offset, gpio_move;
    if (bit_num < 8)
    {
        offset = MODEL_SET_0_7;
        gpio_move = bit_num;
    }
    else if (bit_num < 16)
    {
        offset = MODEL_SET_8_15;
        gpio_move = bit_num - 8;
    }
    else if (bit_num < 24)
    {
        offset = MODEL_SET_16_23;
        gpio_move = bit_num - 16;
    }
    else if (bit_num < 32)
    {
        offset = MODEL_SET_24_31;
        gpio_move = bit_num - 24;
    }
    else if (bit_num < 40)
    {
        offset = MODEL_SET_32_39;
        gpio_move = bit_num - 32;
    }
    else if (bit_num < 48)
    {
        offset = MODEL_SET_40_47;
        gpio_move = bit_num - 40;
    }
    else if (bit_num < 56)
    {
        offset = MODEL_SET_48_55;
        gpio_move = bit_num - 48;
    }
    else if (bit_num < 64)
    {
        offset = MODEL_SET_56_63;
        gpio_move = bit_num - 56;
    }

    if (val == 1)
    {
        *(volatile unsigned char *)(map_base + offset) |= (1 << gpio_move); // 置1（地址写访问），表示GPIO管脚复用为GPIO功能
    }
    else
    {
        *(volatile unsigned char *)(map_base + offset) &= ~(1 << gpio_move); // 置0（地址写访问）,表示GPIO管脚复用为其他功能（如UART、SPI等）
    }

    return 0;
}



// 辅助函数：设置单个GPIO输出值（不改变方向）
static void set_gpio(int gpio, int val)
{
    // 复用已有的 gpio_write 逻辑，但为确保读写一致性，直接调用
    gpio_write(gpio, val);
}

