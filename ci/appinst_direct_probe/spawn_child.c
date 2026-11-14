/* iOS12 diagnostic child: no filesystem, network or installer I/O.
 * It exists only to test whether a sandboxed app can spawn a bundled binary.
 */
int main(void) {
    return 0;
}
