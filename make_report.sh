#!/bin/bash

# Clean up auxiliary files
cleanup() {
    rm -f *.aux *.log *.out *.toc
}

# Run pdflatex multiple times to resolve references
pdflatex to_midi.tex
pdflatex to_midi.tex
pdflatex to_midi.tex

# Clean up auxiliary files but keep the PDF
cleanup

echo "PDF generation complete. Output file: to_midi.pdf" 