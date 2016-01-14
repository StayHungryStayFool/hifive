#!/usr/bin/env python

"""
This is a module contains scripts for finding domains in HiC interaction data.

Concepts
--------

These functions rely on the :class:`HiC` class in conjunction with the :class:`Fend` and :class:`HiCData` classes.


API Documentation
-----------------
"""

import sys

import numpy
import h5py
try:
    from mpi4py import MPI
except:
    pass
try:
    from pyx import *
except:
    pass

import libraries._hic_domains as _hic_domains
from libraries.hmm import HMM
import hic_binning


class TAD( object ):
    """
    """

    def __init__(self, hic, silent=False):
        self.hic = hic
        self.silent = silent

    def __getitem__(self, key):
        """Dictionary-like lookup."""
        if key in self.__dict__:
            return self.__dict__[key]
        else:
            return None

    def __setitem__(self, key, value):
        """Dictionary-like value setting."""
        self.__dict__[key] = value
        return None

    def find_BI_TADs(self, binsize, width, minbins, maxbins, chroms=[]):
        if isinstance(chroms, str):
            chroms = [chroms]
        if len(chroms) == 0:
            chroms = list(self.hic.fends['chromosomes'][...])
        self.binsize = int(binsize)
        self.minsize = self.binsize * max(1, int(minbins))
        self.maxsize = self.binsize * (int(maxbins) + 1)
        self.width = int(width) * self.binsize
        maxsize = self.binsize * (int(maxbins) + int(width) + 1)
        self.TADs = {}
        for chrom in chroms:
            self.TADs[chrom] = []
            if not self.silent:
                print >> sys.stderr, ("\r%s\rFinding heatmap for chromosome %s...") % (' ' * 80, chrom),
            temp = self.hic.cis_heatmap(chrom, binsize=binsize, datatype='enrichment', arraytype='compact',
                                        maxdistance=maxsize, returnmapping=True)
            if temp is None:
                continue
            data, mapping = temp
            print >> sys.stderr, ("\rFinding BI scores for chromosome %s...") % (chrom),
            BIs = numpy.zeros((data.shape[0], maxbins + 1, 2), dtype=numpy.float32)
            BIs.fill(-numpy.inf)
            _hic_domains.find_BIs(data, BIs, minbins, maxbins, width)
            path = numpy.zeros(data.shape[0], dtype=numpy.int32)
            path_scores = numpy.zeros(data.shape[0], dtype=numpy.float64)
            if not self.silent:
                print >> sys.stderr, ("\r%s\rFinding optimal domains for chromosome %s...") % (' ' * 80, chrom),
            _hic_domains.find_BI_path(BIs, path, path_scores, minbins, maxbins)
            i = path.shape[0] - 1
            domains = []
            while i > 0:
                if path[i] != 1:
                    domains.append([i - path[i] + 1, i])
                    self.TADs[chrom].append([mapping[domains[-1][0], 0], mapping[domains[-1][1], 1]])
                i -= path[i]
        if not self.silent:
            print >> sys.stderr, ("\r%s\rFinished finding TADs\n") % (' ' * 80),

    def find_arrowhead_TADs(self, binsize, minbins, maxbins, chroms=[]):
        if isinstance(chroms, str):
            chroms = [chroms]
        if len(chroms) == 0:
            chroms = list(self.hic.fends['chromosomes'][...])
        self.binsize = int(binsize)
        self.minsize = self.binsize * max(1, int(minbins))
        self.maxsize = self.binsize * (int(maxbins) + 1)
        self.TADs = {}
        for chrom in chroms:
            self.TADs[chrom] = []
            if not self.silent:
                print >> sys.stderr, ("\r%s\rFinding heatmap for chromosome %s...") % (' ' * 80, chrom),
            temp = self.hic.cis_heatmap(chrom, binsize=binsize * 16, datatype='fend', arraytype='full', returnmapping=True)
            if temp is None:
                continue
            temp_data, mapping = temp
            heatmap = numpy.zeros((temp_data.shape[0] * 16, temp_data.shape[0] * 16, 2), dtype=numpy.float32)
            temp = numpy.zeros(heatmap.shape, dtype=numpy.float32)
            for i in range(16):
                for j in range(16):
                    heatmap[i::16, j::16, :] += temp_data
            temp_data = self.hic.cis_heatmap(chrom, binsize=binsize * 4, datatype='fend', arraytype='full', start=mapping[0, 0], stop=mapping[-1, 1])
            for i in range(4):
                for j in range(4):
                    temp[i::4, j::4, :] += temp_data
            where = numpy.where(temp[:, :, 0] > 0)
            heatmap[where[0], where[1], :] = temp[where[0], where[1], :]
            temp_data, mapping = self.hic.cis_heatmap(chrom, binsize=binsize, datatype='fend', arraytype='full', start=mapping[0, 0], stop=mapping[-1, 1], returnmapping=True)
            where = numpy.where(temp_data[:, :, 0] > 0)
            heatmap[where[0], where[1], :] = temp_data[where[0], where[1], :]
            data = numpy.zeros((heatmap.shape[0], maxbins - 1, 2), dtype=numpy.float32)
            for i in range(heatmap.shape[0] - 1):
                data[i, :min(data.shape[1], data.shape[0] - i - 1), :] = heatmap[i, (i + 1):min(data.shape[1] + i + 1, data.shape[0]), :]
            where = numpy.where(data[:, :, 1] > 0)
            data[where[0], where[1], 0] /= data[where[0], where[1], 1]
            scores = numpy.zeros((data.shape[0], data.shape[1]), dtype=numpy.float32)
            if not self.silent:
                print >> sys.stderr, ("\r%s\rFinding arrowhead transformation for chromosome %s...") % (' ' * 80, chrom),
            _hic_domains.find_arrowhead_transformation(data, scores, maxbins)
            sums = numpy.zeros(data.shape, dtype=numpy.float32)
            signs = numpy.zeros(data.shape, dtype=numpy.float32)
            variances = numpy.zeros((data.shape[0], data.shape[1], 2, 2), dtype=numpy.float32)
            domain_scores = numpy.zeros(scores.shape, dtype=numpy.float32)
            if not self.silent:
                print >> sys.stderr, ("\r%s\rFinding arrowhead scoring for chromosome %s...") % (' ' * 80, chrom),
            _hic_domains.find_arrowhead_scores(scores, sums, signs, variances, domain_scores, minbins)
            path = numpy.zeros(data.shape[0], dtype=numpy.int32)
            path_scores = numpy.zeros(data.shape[0], dtype=numpy.float64)
            if not self.silent:
                print >> sys.stderr, ("\r%s\rFinding optimal domains for chromosome %s...") % (' ' * 80, chrom),
            _hic_domains.find_arrowhead_path(domain_scores, path, path_scores, minbins, maxbins)
            i = path.shape[0] - 1
            domains = []
            while i > 0:
                if path[i] != 1:
                    domains.append([i - path[i], i])
                    self.TADs[chrom].append([mapping[domains[-1][0], 0], mapping[domains[-1][1], 1]])
                i -= path[i]
        if not self.silent:
            print >> sys.stderr, ("\r%s\rFinished finding TADs\n") % (' ' * 80),

    def find_DI_TADs(self, binsize=20000, step=2500, window=500000, smoothing=6, chroms=[]):
        self.binsize = int(binsize)
        self.step = int(step)
        self.window = int(window)
        self.smoothing = int(smoothing)
        steps = binsize / step
        self.DIs = {}
        self.TADs = {}
        if isinstance(chroms, str):
            chroms = [chroms]
        if len(chroms) == 0:
            chroms = list(self.hic.fends['chromosomes'][...])
        pos_sum = 0.0
        pos_2sum = 0.0
        pos_count = 0
        neg_sum = 0.0
        neg_2sum = 0.0
        neg_count = 0
        training_seqs = []
        for chrom in chroms:
            temp = self.hic.cis_heatmap(chrom, binsize=self.step, maxdistance=self.window, datatype='fend',
                                        arraytype='compact', returnmapping=True)
            if temp is None:
                continue
            num_bins = temp[0].shape[1]
            step0 = []
            step1 = []
            for i in range(steps):
                step0.append(numpy.arange(i, num_bins - steps + 1 + i))
                step1.append(numpy.arange(1 + i, num_bins - steps + 2 + i))
            scores = []
            positions = []
            for i in range(num_bins, temp[0].shape[0] - num_bins - steps + 1):
                observed0 = 0
                expected0 = 0.0
                observed1 = 0
                expected1 = 0.0
                for j in range(steps):
                    observed0 += numpy.sum(temp[0][i + j, step0[steps - j - 1], 0])
                    expected0 += numpy.sum(temp[0][i + j, step0[steps - j - 1], 1])
                    observed1 += numpy.sum(temp[0][i - step1[j], step0[j], 0])
                    expected1 += numpy.sum(temp[0][i - step1[j], step0[j], 1])
                if observed0 > 0 and observed1 > 0:
                    scores.append(numpy.log(observed0 * expected1 / (observed1 * expected0)))
                    positions.append((temp[1][i, 0] + temp[1][i + steps - 1, 1]) / 2)
            self.DIs[chrom] = numpy.zeros(len(scores), dtype=numpy.dtype([('position', numpy.int32),
                                                                          ('score', numpy.float64)]))
            scores = numpy.array(scores)
            if self.smoothing > 1:
                scores *= self.smoothing
                for j in range(1, self.smoothing):
                    scores[j:] += scores[:-j] * (self.smoothing - j)
                    scores[:-j] += scores[j:] * (self.smoothing - j)
                scores[self.smoothing:-self.smoothing] /= self.smoothing ** 2
                for j in range(1, self.smoothing + 1):
                    scores[self.smoothing - j] /= self.smoothing ** 2 - (j * (j + 1)) / 2
                    scores[-self.smoothing + j - 1] /= self.smoothing ** 2 - (j * (j + 1)) / 2
            scores /= numpy.std(scores)
            self.DIs[chrom]['score'] = scores
            self.DIs[chrom]['position'] = positions
            training_seqs.append(numpy.array(scores, dtype=numpy.float64))
            where = numpy.where(self.DIs[chrom]['score'] > 0.0)[0]
            pos_sum += numpy.sum(self.DIs[chrom]['score'][where])
            pos_2sum += numpy.sum(self.DIs[chrom]['score'][where] ** 2)
            pos_count += where.shape[0]
            where = numpy.where(self.DIs[chrom]['score'] < 0.0)[0]
            neg_sum += numpy.sum(self.DIs[chrom]['score'][where])
            neg_2sum += numpy.sum(self.DIs[chrom]['score'][where] ** 2)
            neg_count += where.shape[0]
        pos_mean = pos_sum / pos_count
        pos_var = (pos_2sum / pos_count - pos_mean ** 2.0)
        neg_mean = neg_sum / neg_count
        neg_var = (neg_2sum / neg_count - neg_mean ** 2.0)
        seed = 2001
        pi = [0.45, 0.45, 0.1]
        transitions = [[1.0 - self.step / 250000., self.step / 250000., 0.0],
                       [self.step / 500000., 1.0 - self.step / 250000., self.step / 500000.],
                       [self.step / 50000., 0.0, 1.0 - self.step / 50000.]]
        distributions = [[[0.33, pos_mean * 1.25, pos_var / 2.0],
                          [0.33, pos_mean * 0.75, pos_var / 2.0]],
                          [[0.33, pos_mean * 0.25, pos_var / 2.0],
                          [0.33, neg_mean * 0.25, neg_var / 2.0]],
                          [[0.33, neg_mean * 1.25, neg_var / 2.0],
                          [0.33, neg_mean * 0.75, neg_var / 2.0]]]
        hmm = HMM(
            seed=seed,
            num_states=2,
            num_distributions=2,
            pi=pi,
            transitions=transitions,
            distributions=distributions)
        hmm.train(training_seqs)
        for chrom in chroms:
            if chrom not in self.DIs:
                continue
            states = hmm.find_path(self.DIs[chrom]['score'])[0]
            start = None
            tads = []
            i = 1
            while i < states.shape[0]:
                while i < states.shape[0] and not (states[i - 1] != 0 and states[i] == 0):
                    i += 1
                if i < states.shape[0]:
                    start = self.DIs[chrom]['position'][i] - self.step / 2
                    i += 1
                while i < states.shape[0] and not (states[i] != 1 and states[i - 1] == 1):
                    i += 1
                if i < states.shape[0]:
                    stop = self.DIs[chrom]['position'][i - 1] + self.step / 2
                    tads.append([start, stop])
                    start = None
            self.TADs[chrom] = numpy.array(tads, dtype=numpy.int32)
            where = numpy.where(self.TADs[chrom][1:, 0] < self.TADs[chrom][:-1, 1])[0]
            mids = (self.TADs[chrom][where, 1] + self.TADs[chrom][where + 1, 0]) / 2
            self.TADs[chrom][where, 1] = mids
            self.TADs[chrom][where + 1, 0] = mids

    def plot_DI_tads(self, out_fname):
        if 'pyx' not in sys.modules:
            return None
        unit.set(defaultunit="cm")
        text.set(mode="latex")
        text.preamble(r"\usepackage{times}")
        text.preamble(r"\usepackage{sansmath}")
        text.preamble(r"\sansmath")
        text.preamble(r"\renewcommand*\familydefault{\sfdefault}")
        painter = graph.axis.painter.regular( labeldist=0.1, labelattrs=[text.size(-3)], titleattrs=[text.size(-3)] )
        pages = []
        for chrom in self.DIs:
            start = self.DIs[chrom]['position'][0]
            stop = self.DIs[chrom]['position'][-1]
            max_val = numpy.amax(numpy.abs(self.DIs[chrom]['score'])) * 1.05
            g = graph.graphxy( width=40, height=5,
                x=graph.axis.lin(min=start, max=stop, title='', painter=painter), 
                y=graph.axis.lin(min=-max_val, max=max_val, title='', painter=painter), 
                x2=graph.axis.lin(min=0, max=1, parter=None),
                y2=graph.axis.lin(min=0, max=1, parter=None))
            g.text(40.1, 2.5, chrom, [text.halign.center, text.valign.bottom, trafo.rotate(-90), text.size(-3)])
            g.plot(graph.data.points(zip(self.DIs[chrom]['position'], self.DIs[chrom]['score']), x=1, y=2),
                [graph.style.line([style.linewidth.THIN])])
            g.stroke(path.line(0, 2.5, 40, 2.5), [style.linestyle.dotted, style.linewidth.THIN])
            for i in range(self.TADs[chrom].shape[0]):
                X0 = (self.TADs[chrom][i, 0] - start) / float(stop - start) * 40.0
                X1 = (self.TADs[chrom][i, 1] - start) / float(stop - start) * 40.0
                if i % 2 == 0:
                    Y = 1.25
                else:
                    Y = 3.75
                g.stroke(path.line(X0, Y, X1, Y), [style.linewidth.THICK])
                g.stroke(path.line(X0, 1.25, X0, 3.75), [style.linewidth.THIN, style.linestyle.dotted])
                if i == self.TADs[chrom].shape[0] - 1 or self.TADs[chrom][i, 1] != self.TADs[chrom][i + 1, 0]:
                    g.stroke(path.line(X1, 1.25, X1, 3.75), [style.linewidth.THIN, style.linestyle.dotted])
            pages.append(document.page(self.plot_tads(chrom)))
        doc = document.document(pages)
        doc.writePDFfile(out_fname)    

    def write_TADs(self, fname):
        output = open(fname, 'w')
        chroms = self.TADs.keys()
        chroms.sort()
        for chrom in chroms:
            self.TADs[chrom].sort()
            for domain in self.TADs[chrom]:
                print >> output, "%s\t%i\t%i" % (chrom, domain[0], domain[1])
        output.close()


class Compartment( object ):
    """
    """
    def __init__(self, hic, binsize, chroms=[], out_fname=None):
        self.hic = hic
        self.binsize = binsize
        if 'mpi4py' in sys.modules.keys():
            self.comm = MPI.COMM_WORLD
            self.rank = self.comm.Get_rank()
            self.num_procs = self.comm.Get_size()
        else:
            self.comm = None
            self.rank = 0
            self.num_procs = 1
        if self.rank == 0:
            self.silent = silent
        else:
            self.silent = True
        if self.rank == 0:
            if out_fname is not None:
                storage = h5py.File(out_fname, 'a')
            else:
                storage = None
            needed = []
            if chroms == "" or (isinstance(chroms, list) and len(chroms) == 0):
                chroms = hic.fends['chromosomes'][...]
            self.chroms = chroms
            for chrom in chroms:
                if storage is None or ("%s.correlations" % chrom not in storage and
                                       "%s.enrichments" % chrom not in storage):
                    needed.append(chrom)
                if len(needed) > 0:
                    node_ranges = numpy.round(numpy.linspace(0, len(needed), self.num_procs)).astype(numpy.int32)
                    for i in range(1, self.num_procs):
                        self.comm.send(needed[node_ranges[i]:node_ranges[i + 1]], dest=i, tag=11)
                    node_needed = needed[:node_ranges[1]]
                else:
                    for i in range(1, self.num_procs):
                        self.comm.send([], dest=i, tag=11)
        else:
            node_needed = self.comm.recv(source=0, tag=11)
        data = {}
        self.positions = {}
        chr_indices = hic.fends['chr_indices'][...]
        for chrom in node_needed:
            if self.rank == 0:
                print >> sys.stderr, ("\Heatmapping %s%s") % (chrom, ' '*20),
            chrint = hic.chr2int[chrom]
            startfend = chr_indices[chrint]
            while hic.filter[startfend] == 0:
                startfend += 1
            start = (hic.fends['fends']['mid'][startfend] / binsize) * binsize
            stopfend = chr_indices[chrint + 1]
            while hic.filter[stopfend - 1] == 0:
                stopfend -= 1
            stop = ((hic.fends['fends']['mid'][stopfend - 1] - 1) / binsize + 1) * binsize
            temp = hic.cis_heatmap(chrom, binsize=binsize / 2, start=start, stop=stop, datatype='enrichment',
                                   arraytype='upper', returnmapping=True)
            temp1 = hic_binning.bin_cis_array(temp[0], temp[1], binsize, arraytype='upper', returnmapping=True)
            hic_binning.dynamically_bin_cis_array(temp[0], temp[1], temp1[0], temp1[1], minobservation=5)
            indices = numpy.triu_indices(temp1[1].shape[0], 1)
            hm = numpy.zeros((temp1[1].shape[0], temp1[1].shape[0], 2), dtype=numpy.float32)
            hm[indices[0], indices[1], :] = temp1[0]
            hm[indices[1], indices[0], :] = temp1[0]
            valid = numpy.where(numpy.sum(hm[:, :, 1], axis=0) > 0)[0]
            hm = hm[valid, :, :][:, valid, :]
            where = numpy.where(hm[:, :, 1] > 0)
            hm[where[0], where[1], 0] = numpy.log(hm[where[0], where[1], 0] / hm[where[0], where[1], 1])
            self.positions[chrom] = temp1[1][valid, :]
            data[chrom] = hm[:, :, 0]
        if self.rank == 0:
            for i in range(1, num_procs):
                data.update(self.comm.recv(source=i, tag=11))
                self.positions.update(self.comm.recv(source=i, tag=11))
            if storage is not None:
                for chrom in data:
                    storage.create_dataset(name="%s.enrichments" % chrom, data=data[chrom])
                    storage.create_dataset(name="%s.positons" % chrom, data=self.positions[chrom])
        else:
            self.comm.send(data, dest=0, tag=11)
            del data
            self.comm.send(self.positions, dest=0, tag=11)
        if self.rank == 0:
            for chrom in chroms:
                if chrom not in data and "%s.correlations" % chrom not in storage:
                    data[chrom] = storage["%s.correlations" % chrom][...]
                    self.positions[chrom] = storage["%s.positions" % chrom][...]
            correlations = {}
            for chrom in data:
                print >> sys.stderr, ("\rCorrelating %s%s") % (chrom, ' '*20),
                cdata = numpy.copy(data[chrom])
                for i in range(1, num_procs):
                    comm.send(1, dest=i, tag=11)
                    comm.send(cdata, dest=i, tag=11)
                corr = numpy.zeros(cdata.shape, dtype=numpy.float32)
                self.find_correlations(cdata, corr)
                if storage is not None:
                    storage.create_dataset(name="%s.correlations" % chrom, data=corr)
                correlations[chrom] = corr
        else:
            task = comm.recv(source=0, tag=11)
            while task == 1:
                data = comm.recv(source=0, tag=11)
                self.find_correlations(data)
                task = comm.recv(source=0, tag=11)
        if self.rank == 0:
            self.eigenv = {}
            for chrom in chroms:
                if chrom not in correlations:
                    correlations[chrom] = storage["%s.correlations" % chrom][...]
                self.eigenv[chrom] = scipy.sparse.linalg.eigs(correlations[chrom], k=1)[1][:, 0]
            self.find_clusters()

    def find_correlations(self, data, correlations=None):
        node_ranges = numpy.round(numpy.linspace(0, data.shape[0], self.num_procs + 1)).astype(numpy.int32)
        means = (numpy.sum(data[node_ranges[self.rank]:node_ranges[self.rank + 1], :], axis=1) -
            data[numpy.arange(node_ranges[self.rank], node_ranges[self.rank + 1]),
            numpy.arange(node_ranges[self.rank], node_ranges[self.rank + 1])]) / (data.shape[0] - 1)
        stds = (numpy.sum(data[node_ranges[self.rank]:node_ranges[self.rank + 1], :] ** 2, axis=1) -
            data[numpy.arange(node_ranges[self.rank], node_ranges[self.rank + 1]),
            numpy.arange(node_ranges[self.rank], node_ranges[self.rank + 1])] ** 2) / (data.shape[0] - 1)
        stds = (stds - means ** 2) ** 0.5
        data[node_ranges[self.rank]:node_ranges[self.rank + 1], :] -= means.reshape(-1, 1)
        data[node_ranges[self.rank]:node_ranges[self.rank + 1], :] /= stds.reshape(-1, 1)
        if self.rank == 0:
            for i in range(1, self.num_procs):
                data[node_ranges[i]:node_ranges[i + 1], :] = self.comm.recv(source=i, tag=13)
            for i in range(1, self.num_procs):
                self.comm.Send(data, dest=i, tag=13)
        else:
            self.comm.send(data[node_ranges[self.rank]:node_ranges[self.rank + 1], :], dest=0, tag=13)
            self.comm.Recv(data, source=0, tag=13)
        indices = numpy.triu_indices(data.shape[0], 1)
        node_ranges = numpy.round(numpy.linspace(0, indices[0].shape[0], self.num_procs + 1)).astype(numpy.int32)
        corr = numpy.zeros(node_ranges[self.rank + 1] - node_ranges[self.rank], dtype=numpy.float32)
        for i in range(node_ranges[self.rank], node_ranges[self.rank + 1]):
            a = indices[0][i]
            b = indices[1][i]
            if a > 0:
                corr[i - node_ranges[self.rank]] += numpy.sum(data[a, :a] * data[b, :a])
            if b - a > 1:
                corr[i - node_ranges[self.rank]] += numpy.sum(data[a, (a + 1):b] * data[b, (a + 1):b])
            if b < data.shape[0] - 1:
                corr[i - node_ranges[self.rank]] += numpy.sum(data[a, (b + 1):] * data[b, (b + 1):])
        if self.rank == 0:
            correlations[indices[0][:node_ranges[1]], indices[1][:node_ranges[1]]] = corr
            for i in range(1, self.num_procs):
                corr = self.comm.recv(source=i, tag=11)
                correlations[indices[0][node_ranges[i]:node_ranges[i + 1]],
                             indices[1][node_ranges[i]:node_ranges[i + 1]]] = corr
            correlations[numpy.arange(correlations.shape[0]), numpy.arange(correlations.shape[0])] = 1
            correlations[indices[1], indices[0]] = correlations[indices]
        else:
            self.comm.send(corr, dest=0, tag=11)

    def find_clusters(self):
        means = numpy.zeros(2, dtype=numpy.float64)
        counts = numpy.zeros(2, dtype=numpy.int32)
        observations = []
        for chrom in self.eigenv:
            pos = numpy.where(self.eigenv[chrom] >= 0)[0]
            means[0] += numpy.sum(self.eigenv[chrom][pos])
            counts[0] += pos.shape[0]
            neg = numpy.where(self.eigenv[chrom] < 0)[0]
            means[1] += numpy.sum(self.eigenv[chrom][neg])
            counts[1] += neg.shape[0]
            observations.append(numpy.copy(self.eigenv[chrom]).astype(numpy.float64))
        means /= counts
        distributions = [
            [[0.33, means[0] * 0.5, means[0] / 4.0],
             [0.34, means[0], means[0] / 4.0],
             [0.33, means[0] * 1.5, means[0] / 4.0]],
            [[0.33, means[1] * 0.5, -means[1] / 4.0],
             [0.34, means[1], -means[1] / 4.0],
             [0.33, means[1] * 1.5, -means[1] / 4.0]]]
        transitions = [[0.99, 0.01], [0.01, 0.99]]
        hmm = HMM(num_states=2, num_distributions=3, pi=[0.5, 0.5], distributions=distributions,
                  transitions=transitions, seed=2001)
        hmm.train(observations)
        self.clusters = {}
        for chrom in self.eigenv:
            self.clusters[chrom] = hmm.find_path(self.eigenv[chrom].astype(numpy.float64))[0]

    def write_compartments(self, out_fname):
        outfile = open(out_fname, 'w')
        chroms = self.clusters.keys()
        chroms.sort()
        for chrom in chroms:
            bounds = numpy.r_[0, numpy.where(self.clusters[chrom][1:] != self.clusters[chrom][:-1])[0] + 1,
                              self.clusters[chrom].shape[0]]
            for i in range(bounds.shape[0] - 1):
                j = bounds[i]
                k = bounds[i + 1] - 1
                print >> outfile, "%s\t%i\t%i\t%i" % (chrom, self.positions[chrom][j, 0], self.positions[chrom][k, 1],
                                                      self.clusters[chrom][j])
        outfile.close()
