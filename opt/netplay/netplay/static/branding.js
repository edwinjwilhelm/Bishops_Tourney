(function(){
  const theme = {
    LIGHT: '#f0d9b5', // (240,217,181)
    DARK:  '#b58863', // (181,136,99)
    centerOutline: { color: 'rgb(40,120,40)', width: 5 },
    outerBorder:  { color: '#ffffff', width: 5 },
    corner: {
      colors: {
        WHITE: 'rgb(255,255,255)',
        GREY:  'rgb(160,160,160)',
        BLACK: 'rgb(0,0,0)',
        PINK:  'rgb(255,105,180)'
      },
      strokeWidth: 5,
      strokeColor: 'rgb(40,40,40)',
      blackStrokeOverride: '#ffffff'
    }
  };
  function copyrightCaption(){
    const year = new Date().getFullYear();
    // Prints exactly as in Bishops_Golden.py, year updates automatically
    return `Copyright © 2016-${year} Edwin John Wilhelm "Bishops, The Game" — v1.6.4`;
  }
  window.BISHOPS_BRANDING = {
    boardTheme(){ return theme; },
    copyrightCaption
  };
})();