const fs = require('fs');

function check(file) {
  const content = fs.readFileSync(file, 'utf8');
  console.log('=== Checking:', file, '===');
  console.log('Has .brand-name:', content.includes('brand-name'));
  console.log('Has .word:', content.includes('class="word"') || content.includes("class='word'"));
  console.log('Has #wordDialog:', content.includes('id="wordDialog"'));
  console.log('Has #dlgHindi:', content.includes('id="dlgHindi"'));
  console.log('Has canvas:', content.includes('<canvas'));
  console.log('Has App.next / onContinue:', content.includes('next:') || content.includes('onContinue'));
  console.log('Has .quiz-opt:', content.includes('quiz-opt'));
  
  const keywords = ['express', 'rational', 'standard', 'form', 'positive', 'denominator', 'numerator', 'multiplying', 'entire', 'placed', 'fractions', 'understanding'];
  const missing = [];
  keywords.forEach(kw => {
    if (!content.includes(`"${kw}"`) && !content.includes(`'${kw}'`)) {
      missing.push(kw);
    }
  });
  console.log('Missing critical keywords in WM:', missing);
}

check('Aasha-AI/chapters/RationalNumbers_Class8_MDS.html');
check('Aasha-AI/chapters/ExponentsPowers_Class8_MDS.html');