from pypdf import PdfReader as pdf_reader
from pypdf.errors import PdfReadError
from pathlib import Path
from ast import literal_eval
import argparse
import csv
import re
import os

ignore = 'IGNORE'

def segment(template_text):
    segments = []
    fields = []
    for t in template_text:
        page_fields = [f[1:-1] for f in re.findall('\\{[A-Z0-9_]+\\}', t)]
        page_seg = re.split('\\{[A-Z0-9_]+\\}', t)
        if len(page_seg) != len(page_fields) + 1:
            print('Field count mismatch!')
        segments.append(page_seg)
        fields.append(page_fields)
    return fields, segments

def match_pdf(fields, template, text, filename=None):
    data_dict = {}
    for p in range(len(template)):
        last_end = len(template[p][0])
        for i, segment in enumerate(template[p][1:]):
            loc = text[p].find(segment, last_end)
            if loc == -1:
                print('\nTemplate match failed for file %s on page %d. ' \
                    'Could not find string "%s" (ignoring whitespace). ' \
                    'Data for this page will be invalid.' % (filename, p + 1, segment))
                break
            if fields[p][i] != ignore:
                data_dict[fields[p][i]] = text[p][last_end:loc]
            last_end = loc + len(segment)
        # match = re.match(template[p], text[p])
        # if not match:
        #     print("Template match failed for file %s on page %d" % (filename, p))
        # groups = match.groups()
        # data = {key: val for key, val in zip(fields[p], groups) if key != ignore}
        # data_dict.update(data)
    return data_dict

def main():
    parser = argparse.ArgumentParser(
        prog='PDFReportExtractor',
        description='Extracts data from PDFs of a certain structure',
    )
    parser.add_argument('-t', '--template', type=str, required=True,
                        help='The path to a PDF or previously saved template file to use as a template.')
    parser.add_argument('-d', '--data', action='extend', nargs='*', type=str,
                        help='A folder or multiple folders containing PDF files to be scanned.')
    parser.add_argument('-o', '--output', type=str, default='pdf_data_out.csv',
                        help='The file to write results to. Default is pdf_data_out.csv')
    parser.add_argument('-i', '--image_output', type=str, default=None,
                        help='The folder to save images to. Leave empty to skip saving images.')
    parser.add_argument('-g', '--ignore', type=str, default='IGNORE',
                        help='The name for fields to ignore. Use this for values that change between PDFs but should not be recorded. Default is "IGNORE"')
    args = parser.parse_args()
    print("Loading template")
    if args.template.endswith('.pdf'):
        reader = pdf_reader(args.template)
        temp_text = [re.sub('\\s+', '', page.extract_text()) for page in reader.pages]
        temp_fields, temp_segments = segment(temp_text)
        print("Saving template data")
        with open(args.template[:-4] + '.txt', 'w') as f:
            for page_fields, reg in zip(temp_fields, temp_segments):
                f.write(repr(page_fields) + '\n')
                f.write(repr(reg) + '\n')
    else:
        with open(args.template, 'r') as f:
            template_data = f.read()
        template_data = template_data.split('\n')[:-1]
        temp_fields = template_data[::2]
        temp_fields = [literal_eval(lst) for lst in temp_fields]
        temp_segments = template_data[1::2]
        temp_segments = [literal_eval(seg) for seg in temp_segments]

    if not args.data:
        return

    ignore = args.ignore

    all_fields = []
    for fields in temp_fields:
        all_fields.extend([f for f in fields if f != ignore])
    outfile = open(args.output, 'w')
    writer = csv.DictWriter(outfile, ['pdf_file_path',] + all_fields)
    writer.writeheader()

    print("Beginning data extraction")

    pdf_files = []
    for path in args.data:
        glob_path = Path(path)
        pdf_files.extend(str(p) for p in glob_path.glob('*.pdf'))

    print("Found %d PDF files" % len(pdf_files))

    for pdf_file in pdf_files:
        print("Processing %s" % pdf_file)
        try:
            reader = pdf_reader(pdf_file)
        except FileNotFoundError as e:
            print("Skipping %s: file not found" % pdf_file)
            continue
        except PdfReadError as e:
            print("Skipping %s: %s" % (pdf_file, e))
            continue
        pdf_text = [re.sub('\\s+', '', page.extract_text()) for page in reader.pages]
        data = match_pdf(temp_fields, temp_segments, pdf_text, pdf_file)
        data['pdf_file_path'] = pdf_file
        writer.writerow(data)
        if args.image_output is not None:
            img_out = Path(args.image_output, pdf_file[:-4])
            if not os.path.exists(img_out):
                os.makedirs(img_out)
            for i, page in enumerate(reader.pages):
                for j, img in enumerate(page.images):
                    with open(Path(img_out, 'page_%d_image_%d.png' % (i, j)), 'wb') as img_file:
                        img_file.write(img.data)
    
    outfile.close()
    print("Done.")

if __name__ == "__main__":
    main()