// A minimal Go program for the go tool test: writes a marker file so the
// test can verify go.install() actually built and ran the program.
package main

import "os"

func main() {
	_ = os.WriteFile(os.Args[1], []byte("fogies-test-go-valid"), 0644)
}
