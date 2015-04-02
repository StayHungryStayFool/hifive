#!/usr/bin/env python

import sys
import subprocess
from math import floor, ceil, log10

import numpy
try:
    from pyx import *
except:
    pass

from ..hic import HiC
from ..plotting import plot_compact_array, plot_upper_array, plot_diagonal_from_compact_array
from ..plotting import plot_diagonal_from_upper_array, plot_key


def run(args):
    if not args.image is None and args.pdf and "pyx" not in sys.modules.keys():
        parser.error("-p/--pdf requires the package 'pyx'")
    hic = HiC(args.project, 'r', silent=args.silent)
    if args.stop == 0:
        maxstop = hic.fends['fends']['stop'][hic.fends['chr_indices'][hic.chr2int[args.chrom] + 1] - 1]
    else:
        maxstop = args.stop
    if args.maxdist is None:
        args.maxdist = 0
    if args.maxdist == 0 or args.maxdist >= (maxstop - args.start) / 2:
        arraytype = 'upper'
    else:
        arraytype = 'compact'
    kwargs = {}
    for arg in args.keywords:
        temp = arg.split("=")
        if temp[1] in ["True", "TRUE", "true"]:
            temp[1] = True
        elif temp[1] in ["False", "FALSE", "false"]:
            temp[1] = False
        elif temp[1][0] == "(":
            temp[1] = temp[1].strip('()').split(',')
            for i in range(len(temp[1])):
                temp[1][i] = int(temp[1][i])
            temp[1] = tuple(temp[1])
        elif temp[1][0] == "[":
            temp[1] = temp[1].strip('[]').split(',')
            for i in range(len(temp[1])):
                temp[1][i] = int(temp[1][i])
        else:
            try:
                temp[1] = int(temp[1])
            except:
                # strip off extra characters introduced by galaxy into color format
                temp[1] = temp[1].replace('__pd__','')
        kwargs[temp[0]] = temp[1]
    data, mapping = hic.cis_heatmap(chrom=args.chrom, binsize=args.binsize, start=args.start,
                                    stop=args.stop, datatype=args.datatype, arraytype=arraytype,
                                    maxdistance=args.maxdist, returnmapping=True, skipfiltered=True)
    mapping = mapping[:, :2]
    output = open(args.output, 'w')
    if arraytype == 'upper':
        pos = 0
        for i in range(mapping.shape[0] - 1):
            for j in range(i + 1, mapping.shape[0]):
                if data[pos, 0] > 0.0 and data[pos, 1] > 0.0:
                    print >> output, "chr%s\t%i\t%i\tchr%s\t%i\t%i\t%f" % (args.chrom, mapping[i, 0], mapping[i, 1],
                                                                        args.chrom, mapping[j, 0], mapping[j, 1],
                                                                        numpy.log2(data[pos, 0] / data[pos, 1]))
                pos += 1
    else:
        for i in range(mapping.shape[0] - 1):
            for pos in range(min(mapping.shape[0] - i - 1, data.shape[1])):
                j = i + pos + 1
                if data[i, pos, 0] > 0.0 and data[i, pos, 1] > 0.0:
                    print >> output, "chr%s\t%i\t%i\tchr%s\t%i\t%i\t%f" % (args.chrom, mapping[i, 0], mapping[i, 1],
                                                                        args.chrom, mapping[j, 0], mapping[j, 1],
                                                                        numpy.log2(data[i, pos, 0] / data[i, pos, 1]))
    output.close()
    if not args.image is None:
        if args.datatype == 'enrichment':
            symmetricscaling = True
        else:
            symmetricscaling = False
        if 'symmetricscaling' in kwargs:
            symmetricscaling = kwargs['symmetricscaling']
        if arraytype == 'compact':
            if args.rotate:
                img, minscore, maxscore = plot_diagonal_from_compact_array(data, returnscale=True,
                                          symmetricscaling=symmetricscaling, silent=args.silent, **kwargs)
                offset = 2.5 / (data.shape[0] * 2 - 2)
                height = 2.5
            else:
                img, minscore, maxscore = plot_compact_array(data, returnscale=True,
                                          symmetricscaling=symmetricscaling, silent=args.silent, **kwargs)
                offset = 0.0
                height = 5.0
        else:
            if args.rotate:
                img, minscore, maxscore = plot_diagonal_from_upper_array(data, returnscale=True,
                                          symmetricscaling=symmetricscaling, silent=args.silent, **kwargs)
                offset = 2.5 / (mapping.shape[0] * 2 - 2)
                height = 2.5
            else:
                img, minscore, maxscore = plot_upper_array(data, returnscale=True,
                                          symmetricscaling=symmetricscaling, silent=args.silent, **kwargs)
                offset = 0.0
                height = 5.0
        if args.pdf:
            c = canvas.canvas()
            c1 = canvas.canvas([canvas.clip(path.rect(0, 0, 5, 5))])
            c1.insert(bitmap.bitmap(-offset, -offset, img, width=5.0))
            c.insert(c1)
            if args.ticks and args.binsize > 0:
                c.stroke(path.line(0, 0, 5.0, 0))
                xmin = (mapping[0, 0] + mapping[0, 1]) / 2
                xmax = (mapping[-1, 0] + mapping[-1, 1]) / 2
                order = int(floor(log10(xmax - xmin))) - 1
                step = int(floor((xmax - xmin) / (10.0 ** order * 5.0))) * 10 ** order
                values = numpy.arange(((xmin - 1) / step + 1) * step, (xmax / step) * step + 1, step)
                ticks = (values - float(mapping[0, 0] + mapping[0, 1]) / 2) / (mapping[-1, 0] - mapping[0, 0]) * 5.0
                for i in range(values.shape[0]):
                    c.stroke(path.line(ticks[i], 0, ticks[i], -0.25), [style.linewidth.Thin])
                    c.text(ticks[i], -0.3, "%0.2e" % values[i], [text.valign.middle, text.halign.left, text.size(-2),
                                                              trafo.rotate(-90)])
                if not args.rotate:
                    c.stroke(path.line(5.0, 0, 5.0, 5.0))
                    for i in range(values.shape[0]):
                        c.stroke(path.line(5.0, 5.0 - ticks[i], 5.25, 5.0 - ticks[i]), [style.linewidth.Thin])
                        c.text(5.3, 5.0 - ticks[i], "%0.2e" % values[i], [text.valign.middle, text.halign.left,
                                                                          text.size(-2)])
            if args.legend:
                if 'min_color' in kwargs:
                    min_color = kwargs['min_color']
                else:
                    min_color = "0000ff"
                if 'mid_color' in kwargs:
                    mid_color = kwargs['mid_color']
                else:
                    mid_color = "ffffff"
                if 'max_color' in kwargs:
                    max_color = kwargs['max_color']
                else:
                    max_color = "ff0000"
                if 'logged' in kwargs:
                    logged = kwargs['logged']
                else:
                    logged = True
                c.insert(plot_key(min_score=minscore, max_score=maxscore, height=0.25, width=5.0,
                                  orientation='top', num_ticks=5, min_color=min_color,
                                  mid_color=mid_color, max_color=max_color,
                                  log_display=False), [trafo.translate(0, height + 0.25)])
                if logged:
                    label = "Log2 "
                else:
                    label = ""
                if args.datatype == 'enrichment':
                    c.text(2.5, height + 0.8, "%sEnrichment" % label, [text.halign.center, text.valign.bottom,
                                                                       text.size(-2)])
                elif args.datatype == 'raw':
                    c.text(2.5, height + 0.8, "%sCounts" % label, [text.halign.center, text.valign.bottom,
                                                                   text.size(-2)])
                else:
                    c.text(2.5, height + 0.8, "%sNormalized Counts" % label, [text.halign.center, text.valign.bottom,
                                                                              text.size(-2)])

            c.writePDFfile(args.image)
            if len(args.image.split('.')) <= 1 or args.image.split('.')[-1] != 'pdf':
                subprocess.call('mv %s.pdf %s' % (args.image, args.image), shell=True)

        else:
            img.save(args.image)
