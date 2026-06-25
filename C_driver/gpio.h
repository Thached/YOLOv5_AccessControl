/**
 * @brief gpio.h
 *
 */
#define MAP_SIZE 0x10000
#define REG_BASE 0x1fe10000 // 龙芯2K1000用户手册，GPIO配置寄存器基地址

#define GPIO_EN 0x500  // GPIO0_OEN（GPIO方向控制（GPIO输出使能），0为输出，1为输入）地址：0x1fe10500
#define GPIO_OUT 0x510 // GPIO0_O（GPIO 输出值）地址：0x1fe10510
#define GPIO_IN 0x520  // GPIO0_I（GPIO 输入值）地址：0x1fe10520

extern int file;

extern unsigned char *map_base;

/**
 * @brief gpio初始化（建立GPIO和虚拟内存的映射关系）
 *
 * @return int 成功，返回0；失败，返回-1。
 */
int gpio_init(void);

/**
 * @brief gpio端口使能
 *
 * @param gpio_num 使能GPIO的端口号（0～63）
 * @param val 0——GPIO使能in（输入）；1——GPIO使能out（输出）。
 * @return int 成功，返回0。
 */
int gpio_enable(int gpio_num, int val);

/**
 * @brief gpio关闭（解除映射关系）
 *
 * @return int 成功，返回0；失败，返回-1。
 */
int gpio_close(void);

/**
 * @brief gpio写入
 *
 * @param gpio gpio端口号（0～63）
 * @param val 1——高电平；0——低电平。
 * @return int 成功，返回0
 */
int gpio_write(int gpio, int val);

/**
 * @brief gpio读取
 *
 * @param gpio_num gpio端口号（0～63）
 * @return int 1——高电平；0——低电平。
 */
int gpio_read(int gpio_num);

/**
 * @brief gpio管脚复用模式设置
 *
 * @param bit_num 位编号
 * @param val 位值：1——高电平；0——低电平。
 * @return int 成功，返回0
 */
int gpio_model_set(int bit_num, int val);








// 管脚复用
// loongson2k1000_user 用户手册 表 5-2 通用配置寄存器 0
// 通用配置寄存器 0，包括对管脚复用的控制，以及HDA、USB、PCIE 的一致性、内存控制器、RTC 控制器及 LIO 控制器的配置等。//
#define MODEL_SET_0_7 0x420 
#define MODEL_SET_8_15 0x421
#define MODEL_SET_16_23 0x422
#define MODEL_SET_24_31 0x423
#define MODEL_SET_32_39 0x424
#define MODEL_SET_40_47 0x425
#define MODEL_SET_48_55 0x426
#define MODEL_SET_56_63 0x427