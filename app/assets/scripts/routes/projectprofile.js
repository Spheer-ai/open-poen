export default {
    init() {
        const justify = "#justify-interactive-form"
        $(justify).find(".funder-info").slice(1).hide();
        $(justify).find("[type=radio]").on("click", function () {
            $(justify).find(".funder-info").hide()
            $(justify).find("#funder-info-" + this.value).show()

            const links = $(".report-link")
            let pattern = new RegExp("funder/" + "\\d+")
            links.attr("href", links.attr("href").replace(pattern, "funder/" + this.value))
        })

        const concept = "#concept-justify-interactive-form"
        $(concept).find(".funder-info").slice(1).hide();
        $(concept).find("[type=radio]").on("click", function () {
            $(concept).find(".funder-info").hide()
            $(concept).find("#funder-info-" + this.value).show()

            const links = $(".concept-report-link")
            let pattern = new RegExp("funder/" + "\\d+")
            links.attr("href", links.attr("href").replace(pattern, "funder/" + this.value))
        })
    },
    finalize() {
        // JavaScript to be fired on the home page, after the init JS
    },
};
