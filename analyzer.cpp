#include <iostream>
#include <string>

int main() {
    std::string line;
    int line_count = 0;
    int char_count = 0;

    // 不断读取 Python 塞过来的代码，直到读完
    while (std::getline(std::cin, line)) {
        line_count++;
        char_count += line.length();
    }

    std::cout << "正在调用C++" << std::endl;
    std::cout << "- 物理行数: " << line_count << " 行" << std::endl;
    std::cout << "- 总字符数: " << char_count << " 字符" << std::endl;

    return 0;
}