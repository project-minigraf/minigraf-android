package io.github.project_minigraf.benchmark

/** Conservative runtime classification; ambiguity is never physical evidence. */
object PlatformIdentity {
    fun classify(fingerprint: String, hardware: String, product: String,
                 kernelQemu: String, bootQemu: String, abis: List<String>,
                 model: String, sdk: Int, loadedAbi: String): String {
        if (listOf(fingerprint, hardware, product, model).any { it.isBlank() } ||
            sdk < 24 || loadedAbi !in abis || loadedAbi !in listOf("arm64-v8a", "x86_64")) return "unknown"
        val qemu = kernelQemu == "1" || bootQemu == "1"
        val virtualHardware = hardware.lowercase() in listOf("ranchu", "goldfish", "qemu", "vbox86")
        val virtualProduct = listOf(product, fingerprint, model).any {
            val value = it.lowercase()
            listOf("sdk", "emulator", "generic", "vbox", "goldfish", "ranchu").any(value::contains)
        }
        val contradictory = kernelQemu !in listOf("", "0", "1") || bootQemu !in listOf("", "0", "1") ||
            (kernelQemu == "1" && bootQemu == "0") || (kernelQemu == "0" && bootQemu == "1")
        if (contradictory) return "unknown"
        if (qemu && (virtualHardware || virtualProduct)) return "emulator"
        if (!qemu && !virtualHardware && !virtualProduct && loadedAbi == "arm64-v8a" &&
            fingerprint.contains("/") && fingerprint.contains(":")) return "physical"
        return "unknown"
    }

    fun elfAbi(header: ByteArray): String {
        require(header.size >= 20 && header[0] == 0x7f.toByte() && header[1] == 69.toByte() &&
            header[2] == 76.toByte() && header[3] == 70.toByte() && header[4] == 2.toByte() &&
            header[5] == 1.toByte()) { "expected little-endian ELF64 native library" }
        return when ((header[18].toInt() and 255) or ((header[19].toInt() and 255) shl 8)) {
            183 -> "arm64-v8a"
            62 -> "x86_64"
            else -> throw IllegalArgumentException("unsupported loaded ELF machine")
        }
    }
}
