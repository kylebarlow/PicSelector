var openPhotoSwipe = function(mediaIndex) {
    var pswpElement = document.querySelectorAll('.pswp')[0];
    
    // define options (if needed)
    var options = {
      	// history: false,
      	// focus: false,

        showAnimationDuration: 0,
        hideAnimationDuration: 0,
        index: mediaIndex // start at first slide
    };
    
    var gallery = new PhotoSwipe( pswpElement, PhotoSwipeUI_Default, items, options);
    gallery.init();
};

function clickVoteYes() {
    var mediaid = $( this ).parent().parent().data("mediaid")
    clickVote(1, mediaid)
};

function clickVoteNo() {
    var mediaid = $( this ).parent().parent().data("mediaid")
    clickVote(-1, mediaid)
};

function clickVote(votevalue, mediaid) {
$.ajax({
    method: 'POST',
    url: $SCRIPT_ROOT + '/_vote',
    data: {votevalue: votevalue, mediaid: mediaid}
}).done(showVote);
};

function showVote(data) {
    var voteyestag = $( "#vote-yes-" + data.mediaid.toString() )
    var votenotag = $( "#vote-no-" + data.mediaid.toString() )
    console.log("#vote-yes-" + data.mediaid.toString())
    if ( data.votevalue == -1 ) {
        if(voteyestag[0].classList.contains('fas')) {
            voteyestag.attr("class", "far fa-star fa-4x")
        }
        if(votenotag[0].classList.contains('far')) {
            votenotag.attr("class", "fas fa-trash-alt fa-4x")
        }
    } else if ( data.votevalue == 1 ) {
        if(voteyestag[0].classList.contains('far')) {
            voteyestag.attr("class", "fas fa-star fa-4x")
        }
        if(votenotag[0].classList.contains('fas')) {
            votenotag.attr("class", "far fa-trash-alt fa-4x")
        }
    } else if ( data.votevalue == 0 ) {
        if(voteyestag[0].classList.contains('fas')) {
            voteyestag.attr("class", "far fa-star fa-4x")
        }
        if(votenotag[0].classList.contains('fas')) {
            votenotag.attr("class", "far fa-trash-alt fa-4x")
        }
    }
    
    console.log(data.votevalue)
}

$("[id^=vote-yes]").click(clickVoteYes);
$("[id^=vote-no]").click(clickVoteNo);