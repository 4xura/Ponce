// Use the plugin's native struct layout for disposable autonomous test sessions.
#include "globals.hpp"
#include <fstream>

int main(int argc, char **argv)
{
    if (argc != 2)
        return 1;
    cmdOptionStruct options{};
    options.already_configured = true;
    options.use_symbolic_engine = true;
    options.showDebugInfo = true;
    std::ofstream output(argv[1], std::ios::binary);
    output.write(reinterpret_cast<const char *>(&options), sizeof(options));
    return output.good() ? 0 : 1;
}
