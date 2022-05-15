export default {
    init() {
        const justify = "#justify-interactive-form"
        const concept = "#concept-justify-interactive-form"
        $(justify).find(".funder-info").slice(1).hide();
        $(justify).find("[type=radio]").on("click", function () {
            $(justify).find(".funder-info").hide()
            $(justify).find("#funder-info-" + this.value).show()
        })
        $(concept).find(".funder-info").slice(1).hide();
        $(concept).find("[type=radio]").on("click", function () {
            $(concept).find(".funder-info").hide()
            $(concept).find("#funder-info-" + this.value).show()
        })
    },
    finalize() {
        // JavaScript to be fired on the home page, after the init JS
    },
};
