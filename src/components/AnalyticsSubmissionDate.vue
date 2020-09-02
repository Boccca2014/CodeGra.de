<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<b-card class="analytics-submission-date"
        header-class="d-flex"
        :body-class="noSubmissionWithinRange ? 'center' : ''">
    <template #header>
        <div class="flex-grow-1">
            Students submitted on
        </div>

        <div class="d-flex flex-grow-0">
            <b-button :variant="settings.relative ? 'primary' : 'outline-primary'"
                      @click="toggleRelative()"
                      v-b-popover.top.hover="relativePopoverText"
                      class="ml-3">
                <icon name="percent" />
            </b-button>

            <datetime-picker :value="settings.range"
                             @on-close="updateRange"
                             placeholder="Select dates"
                             :config="{
                                 mode: 'range',
                                 enableTime: false,
                                 minDate: minDate.toISOString(),
                                 maxDate: maxDate.toISOString(),
                             }"
                             class="ml-2 text-center"/>

            <b-input-group class="mb-0">
                <input :value="settings.binSize"
                        @input="updateBinSize"
                        type="number"
                        min="1"
                        step="1"
                        class="form-control ml-2 pt-1"
                        style="max-width: 4rem;"/>

                <b-form-select :value="settings.binUnit"
                                @input="updateBinUnit"
                                :options="binUnits"
                                class="pt-1"
                                style="max-width: 7.5rem"/>
            </b-input-group>

            <div class="icon-button danger ml-2"
                 @click="resetParams"
                 v-b-popover.top.hover="'Reset'">
                <icon name="reply" />
            </div>

            <description-popover class="icon-button pl-0"
                                 placement="bottom"
                                 :scale="1">
                <p class="mb-2">
                    This histogram shows at what times students submitted their
                    work. You can change the range of dates that is displayed
                    and the bin size of the histogram.
                </p>

                <p>
                    See
                    <a href="https://docs.codegra.de/user/analytics-dashboard.html#submission-statistics"
                       target="_blank"
                        >the documentation</a>
                    for more details.
                </p>
            </description-popover>
        </div>
    </template>

    <template v-if="noSubmissionWithinRange">
        <h3 class="p-3 text-muted font-italic">
            No submissions within this range!
        </h3>
    </template>

    <template v-else-if="tooManyBins && !forceRender">
        <p class="p-3 text-muted font-italic">
            The selected range contains a lot of data points and rendering the
            graph may freeze your browser.  Please select fewer bins or click
            the button below to render the dataset anyway.
        </p>

        <b-button variant="primary"
                  class="float-right"
                  @click="forceRender = true">
            Render anyway
        </b-button>
    </template>

    <bar-chart v-else
               :chart-data="histogramData"
               :options="histogramOptions"
               :width="300"
               :height="$root.$isXLargeWindow ? 75 : 100"/>
</b-card>
</template>

<script>
import moment from 'moment';
import * as stat from 'simple-statistics';

import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/percent';
import 'vue-awesome/icons/reply';

import { deepEquals, filterObject } from '@/utils';

import { BarChart } from '@/components/Charts';
import DatetimePicker from '@/components/DatetimePicker';
import DescriptionPopover from '@/components/DescriptionPopover';

function fillSettings(settings) {
    return Object.assign(
        {
            relative: true,
            range: [],
            binSize: 1,
            binUnit: 'days',
        },
        settings,
    );
}

export default {
    name: 'analytics-submission-date',

    props: {
        value: {
            type: Object,
            default: {},
        },
        filterResults: {
            type: Array,
            required: true,
        },
    },

    data() {
        return {
            settings: fillSettings(this.value),

            // Changing the submission date bin size can cause a lot of
            // bins to be drawn, especially when typing something like
            // `10`, where the value is temporarily `1`. We debounce the
            // event of the bin size input with this timer to prevent
            // temporary page freezes or flickering of the "too many bins"
            // message when editing the bin size.
            binSizeTimer: null,

            // When there are a lot of datapoints to draw in a chart the
            // browser may freeze, so we put a soft cap at 100. Users can
            // still choose to render the chart anyway, in which case this
            // boolean is temporarily set to true.
            forceRender: false,
        };
    },

    computed: {
        filterLabels() {
            return this.filterResults.map(f => f.filter.toString());
        },

        submissionSources() {
            return this.filterResults.map(r => r.submissions);
        },

        relativePopoverText() {
            if (this.settings.relative) {
                return 'Show amount of submissions in filter group';
            } else {
                return 'Show percentage of submissions of filter group';
            }
        },

        minDate() {
            const firstPerSource = this.submissionSources.map(source => source.firstSubmissionDate);
            return firstPerSource
                .reduce((f, d) => (f == null || f.isAfter(d) ? d : f), null)
                .clone()
                .local()
                .startOf('day');
        },

        maxDate() {
            const lastPerSource = this.submissionSources.map(source => source.lastSubmissionDate);
            return lastPerSource
                .reduce((l, d) => (l == null || l.isBefore(d) ? d : l), null)
                .clone()
                .local()
                .endOf('day');
        },

        binUnits() {
            return ['minutes', 'hours', 'days', 'weeks'];
        },

        noSubmissionWithinRange() {
            const datasets = this.histogramData.datasets;
            return stat.sum([].concat(...datasets.map(ds => ds.data))) === 0;
        },

        tooManyBins() {
            return this.histogramData.labels.length > 100;
        },

        // TODO: Move this to a FilterResultSet model.
        histogramData() {
            const subs = this.submissionSources.map(source =>
                source.binSubmissionsByDate(
                    this.settings.range,
                    this.settings.binSize,
                    this.settings.binUnit,
                ),
            );

            const format = this.dateFormatter;
            const dateLookup = subs.reduce((acc, bins) => {
                Object.values(bins).forEach(bin => {
                    if (!acc[bin.start]) {
                        acc[bin.start] = format(bin.start, bin.end);
                    }
                });
                return acc;
            }, {});
            const allDates = Object.keys(dateLookup).sort();

            const datasets = subs.map((bins, i) => {
                const absData = allDates.map(d => (bins[d] == null ? 0 : bins[d].data.length));
                const nSubs = stat.sum(absData);
                const relData = absData.map(x => (nSubs > 0 ? 100 * x / nSubs : 0));

                return {
                    label: this.filterLabels[i],
                    absData,
                    relData,
                    data: this.settings.relative ? relData : absData,
                };
            });

            return {
                labels: allDates.map(k => dateLookup[k]),
                datasets,
            };
        },

        dateFormatter() {
            const unit = this.settings.binUnit;

            const format = (d, fmt) =>
                // The times reported per bin are UTC UNIX epoch timestamps.
                moment(d)
                    .utc()
                    .format(fmt);

            switch (unit) {
                case 'minutes':
                    return start => format(start, 'ddd DD-MM HH:mm');
                case 'hours':
                    return start => format(start, 'ddd DD-MM HH:00');
                default:
                    return (start, end) => {
                        const fmt = 'ddd DD-MM';
                        const s = format(start, fmt);
                        const e = format(end, fmt);
                        return s === e ? s : `${s} — ${e}`;
                    };
            }
        },

        histogramOptions() {
            const getDataset = (tooltipItem, data) => data.datasets[tooltipItem.datasetIndex];

            const label = (tooltipItem, data) => {
                const ds = getDataset(tooltipItem, data);
                return ds.label;
            };

            const afterLabel = (tooltipItem, data) => {
                const ds = getDataset(tooltipItem, data);
                const abs = ds.absData[tooltipItem.index];
                const rel = ds.relData[tooltipItem.index];

                // Do not escape, chart.js does its own escaping.
                return [
                    `Number of submissions: ${abs}`,
                    `Percentage of submissions: ${this.to2Dec(rel)}`,
                ];
            };

            const labelString = this.settings.relative
                ? 'Percentage of submissions'
                : 'Number of submissions';

            return {
                scales: {
                    yAxes: [
                        {
                            ticks: {
                                beginAtZero: true,
                            },
                            scaleLabel: {
                                display: true,
                                labelString,
                            },
                        },
                    ],
                },
                tooltips: {
                    callbacks: { label, afterLabel },
                },
            };
        },
    },

    methods: {
        resetParams() {
            this.settings = fillSettings({});
            this.forceRender = false;
            clearTimeout(this.binSizeTimer);
        },

        toggleRelative() {
            this.updateSetting('relative', !this.settings.relative);
        },

        updateRange(event) {
            const curRange = this.settings.range;
            const newRange = event.map(d => moment(d));

            if (
                newRange.length !== curRange.length ||
                // Check if all the dates are the same as the previous to
                // prevent a rerender, e.g. in case a user just opened the
                // popover and immediately closes it by clicking somewhere
                // in the page.
                !newRange.every((d, i) => d.isSame(curRange[i]))
            ) {
                this.forceRender = false;
                this.updateSetting('range', event);
            }
        },

        updateBinSize(event) {
            clearTimeout(this.binSizeTimer);
            this.binSizeTimer = setTimeout(() => {
                const newSize = parseFloat(event.target.value);
                if (!Number.isNaN(newSize) && newSize !== this.settings.binSize && newSize > 0) {
                    this.updateSetting('binSize', Number(newSize));
                    this.forceRender = false;
                }
            }, 500);
        },

        updateBinUnit(unit) {
            this.forceRender = false;
            this.updateSetting('binUnit', unit);
        },

        updateSetting(name, value) {
            if (!this.$utils.hasAttr(this.settings, name)) {
                throw new Error(`Invalid setting: ${name}`);
            }
            this.settings = Object.assign({}, this.settings, { [name]: value });
        },

        to2Dec(x) {
            return this.$utils.toMaxNDecimals(x, 2);
        },
    },

    watch: {
        settings: {
            immediate: true,
            handler() {
                const defaults = fillSettings({});
                const settings = filterObject(
                    this.settings,
                    (val, key) => !deepEquals(val, defaults[key]),
                );
                this.$emit('input', settings);
            },
        },
    },

    components: {
        Icon,
        BarChart,
        DatetimePicker,
        DescriptionPopover,
    },
};
</script>
